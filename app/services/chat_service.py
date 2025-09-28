# app/services/chat_service.py
import uuid
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.core.config import settings
from app.services.retrieval_service import retrieval_service
from app.services.llm_service import llm_service
from app.services.document_service import document_service
from app.models.chat import (
    ChatMessage,
    ChatSession,
    ChatRequest,
    ChatResponse,
    SessionStartRequest,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Legal chatbot service for Indian lawyers - domain-focused conversations"""

    def __init__(self):
        self.sessions: Dict[str, ChatSession] = {}
        self.retrieval_service = retrieval_service
        self.llm_service = llm_service
        self.document_service = document_service
        # Add session storage
        self.storage_file = os.path.join(
            settings.chroma_persist_directory, "sessions.json"
        )
        self._load_sessions()

    def start_session_with_documents(self, request: SessionStartRequest) -> ChatSession:
        """Start a new chat session with specific legal documents"""
        try:
            # Validate that all documents exist and are ready
            valid_documents = []
            document_metadata = {}

            for doc_id in request.document_ids:
                document = self.document_service.get_document(doc_id)
                if document and document.status.value == "ready":
                    # Validate document is legal-related
                    if self._is_legal_document(document):
                        valid_documents.append(doc_id)
                        document_metadata[doc_id] = {
                            "filename": document.metadata.original_filename,
                            "upload_time": document.metadata.upload_timestamp.isoformat(),
                            "word_count": document.metadata.word_count,
                            "chunk_count": len(document.chunks),
                        }
                    else:
                        logger.warning(f"Document {doc_id} does not appear to be legal-related")
                else:
                    logger.warning(f"Document {doc_id} not found or not ready")

            if not valid_documents:
                raise ValueError("No valid legal documents found for session")

            # Create session
            session_id = request.session_id or str(uuid.uuid4())
            session_name = (
                request.session_name or f"Legal Consultation ({len(valid_documents)} documents)"
            )

            session = ChatSession(
                session_id=session_id,
                created_at=datetime.now(),
                last_activity=datetime.now(),
                message_count=0,
                messages=[],
                active_document_ids=valid_documents,
                session_name=session_name,
                document_context=document_metadata,
            )

            self.sessions[session_id] = session
            logger.info(
                f"Started legal session {session_id} with {len(valid_documents)} documents"
            )

            # Save sessions after creation
            self._save_sessions()
            return session

        except Exception as e:
            logger.error(f"Error starting legal session: {str(e)}")
            raise Exception(f"Failed to start legal session: {str(e)}")

    def _is_legal_document(self, document) -> bool:
        """Check if document contains legal content"""
        # Sample content from document to check
        sample_content = ""
        if document.chunks:
            sample_content = " ".join([chunk.content for chunk in document.chunks[:3]])  # First 3 chunks
        
        filename = document.metadata.original_filename.lower()
        
        # Legal indicators in filename
        legal_filename_keywords = [
            'act', 'law', 'legal', 'statute', 'regulation', 'code', 'constitution',
            'judgment', 'case', 'court', 'supreme', 'high court', 'tribunal',
            'ipc', 'crpc', 'cpc', 'evidence', 'contract', 'agreement', 'petition',
            'bail', 'appeal', 'writ', 'divorce', 'property', 'criminal', 'civil'
        ]
        
        # Legal indicators in content
        legal_content_keywords = [
            'section', 'article', 'clause', 'sub-section', 'paragraph',
            'supreme court', 'high court', 'district court', 'magistrate',
            'indian penal code', 'constitution of india', 'civil procedure',
            'criminal procedure', 'evidence act', 'contract act',
            'plaintiff', 'defendant', 'petitioner', 'respondent',
            'judgment', 'order', 'decree', 'injunction', 'mandamus',
            'habeas corpus', 'certiorari', 'prohibition', 'quo warranto',
            'bail', 'anticipatory bail', 'fir', 'chargesheet', 'appeal',
            'revision', 'review', 'criminal', 'civil', 'family', 'property'
        ]
        
        # Check filename
        filename_has_legal = any(keyword in filename for keyword in legal_filename_keywords)
        
        # Check content
        content_has_legal = any(keyword in sample_content.lower() for keyword in legal_content_keywords)
        
        is_legal = filename_has_legal or content_has_legal
        
        if not is_legal:
            logger.warning(f"Document {document.metadata.original_filename} does not appear to contain legal content")
        
        return is_legal

    async def process_chat_message(self, request: ChatRequest) -> ChatResponse:
        """Process a legal chat message with strict domain boundaries"""
        try:
            start_time = datetime.now()

            # First, validate if the query is legal-related
            is_legal_query = await self._is_legal_query(request.message)
            if not is_legal_query:
                return self._create_out_of_scope_response(request, start_time)

            # Get or create session
            session = self._get_or_create_session(request.session_id)

            logger.info(f"Processing legal query in session {session.session_id}")

            # Add user message to session
            user_message = ChatMessage(
                role="user", content=request.message, timestamp=datetime.now()
            )
            session.messages.append(user_message)

            # Determine which documents to search
            search_document_ids = self._determine_search_documents(request, session)

            logger.info(f"Searching in legal documents: {search_document_ids}")

            # Retrieve relevant document chunks
            retrieved_chunks = await self.retrieval_service.retrieve_relevant_chunks(
                query=request.message,
                document_ids=search_document_ids,
                top_k=5,
                min_similarity=0.3,
            )

            logger.info(f"Retrieved {len(retrieved_chunks)} relevant legal chunks")

            # Determine response strategy based on legal context
            response_strategy = self._determine_legal_response_strategy(
                request.message, retrieved_chunks, session
            )

            # Prepare conversation history for context
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in session.messages[-request.max_history :]
                if msg.role == "user"
            ][:-1]  # Exclude current message

            # Generate LLM response with legal context
            llm_result = await self._generate_legal_response(
                request.message,
                retrieved_chunks,
                conversation_history,
                session,
                response_strategy
            )

            # Create assistant message
            assistant_message = ChatMessage(
                role="assistant",
                content=llm_result["response"],
                timestamp=datetime.now(),
                sources=llm_result["sources"],
            )
            session.messages.append(assistant_message)

            # Auto-rename session after first exchange (Claude-like behavior)
            if session.session_name == "New Legal Chat" and session.message_count == 0:
                new_name = self._generate_legal_session_name(
                    request.message, session.document_context
                )
                session.session_name = new_name
                logger.info(f"Auto-renamed legal session to: {new_name}")

            # Update session stats
            session.last_activity = datetime.now()
            session.message_count += 2  # User + assistant messages

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Create response
            response = ChatResponse(
                response=llm_result["response"],
                session_id=session.session_id,
                sources=llm_result["sources"],
                processing_time=processing_time,
                model_used=llm_result["model_used"],
            )

            logger.info(f"Legal chat message processed in {processing_time:.2f}s")

            # Save sessions after processing
            self._save_sessions()
            return response

        except Exception as e:
            logger.error(f"Error processing legal chat message: {str(e)}")
            raise Exception(f"Legal chat processing failed: {str(e)}")

    async def _is_legal_query(self, query: str) -> bool:
        """Check if the query is related to legal matters"""
        legal_keywords = [
            # General legal terms
            'law', 'legal', 'court', 'judge', 'lawyer', 'advocate', 'attorney',
            'case', 'judgment', 'order', 'decree', 'ruling', 'verdict',
            
            # Indian legal system
            'indian law', 'indian constitution', 'supreme court', 'high court',
            'district court', 'magistrate', 'tribunal', 'bar council',
            
            # Legal procedures
            'section', 'article', 'clause', 'act', 'rule', 'regulation',
            'petition', 'appeal', 'revision', 'review', 'bail', 'fir',
            'chargesheet', 'summons', 'warrant', 'notice',
            
            # Legal areas
            'criminal', 'civil', 'family', 'property', 'contract', 'tort',
            'constitutional', 'administrative', 'tax', 'corporate', 'labor',
            'intellectual property', 'cyber', 'environmental',
            
            # Legal documents
            'agreement', 'contract', 'deed', 'will', 'power of attorney',
            'affidavit', 'complaint', 'response', 'counter', 'evidence',
            
            # Rights and remedies
            'rights', 'remedy', 'compensation', 'damages', 'injunction',
            'mandamus', 'habeas corpus', 'certiorari', 'prohibition'
        ]
        
        query_lower = query.lower()
        
        # Check for direct legal keywords
        has_legal_keywords = any(keyword in query_lower for keyword in legal_keywords)
        
        # If no obvious keywords, use LLM for deeper analysis
        if not has_legal_keywords:
            classification_prompt = f"""
            You are a legal domain classifier for an Indian legal chatbot.
            
            Determine if this query is related to law, legal matters, or Indian legal system.
            
            Query: "{query}"
            
            Answer only: YES (if legal-related) or NO (if not legal-related)
            """
            
            try:
                result = await self.llm_service.generate_response(
                    query=classification_prompt,
                    retrieved_chunks=[],
                    conversation_history=[],
                    max_tokens=5
                )
                
                is_legal = "yes" in result.get("response", "").lower()
                logger.info(f"LLM classification for '{query[:50]}...': {'Legal' if is_legal else 'Non-legal'}")
                return is_legal
                
            except Exception as e:
                logger.error(f"Error in LLM legal classification: {e}")
                # If LLM fails, be conservative and allow the query
                return True
        
        return has_legal_keywords

    def _create_out_of_scope_response(self, request: ChatRequest, start_time: datetime) -> ChatResponse:
        """Create response for non-legal queries"""
        out_of_scope_message = """
        I am a specialized legal assistant designed to help Indian lawyers with legal matters. 
        
        I can only answer questions related to:
        • Indian laws and legal procedures
        • Case law and legal precedents  
        • Legal documentation and drafting
        • Court procedures and filing requirements
        • Legal research and analysis
        
        Please ask me questions related to Indian law or legal practice. If you have uploaded legal documents, I can help analyze and explain them.
        """
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ChatResponse(
            response=out_of_scope_message.strip(),
            session_id=request.session_id or str(uuid.uuid4()),
            sources=[],
            processing_time=processing_time,
            model_used="domain_filter"
        )

    def _determine_legal_response_strategy(
        self, query: str, retrieved_chunks: List, session: ChatSession
    ) -> str:
        """Determine how to respond based on legal context"""
        query_lower = query.lower()
        
        # Check if we have relevant document chunks
        has_relevant_docs = retrieved_chunks and any(
            chunk.get("similarity_score", 0) > 0.5 for chunk in retrieved_chunks
        )
        
        if has_relevant_docs:
            # Document-specific legal queries
            if any(word in query_lower for word in ['section', 'article', 'clause', 'provision']):
                return "legal_document_analysis"
            elif any(word in query_lower for word in ['case', 'judgment', 'precedent']):
                return "case_law_analysis"
            else:
                return "document_based_legal_advice"
        
        else:
            # No relevant documents, but still legal query - use LLM knowledge
            if any(word in query_lower for word in ['section', 'ipc', 'crpc', 'cpc', 'article']):
                return "legal_statute_explanation"  # New strategy for statutory law
            elif any(word in query_lower for word in ['case', 'judgment', 'precedent', 'supreme court']):
                return "case_law_knowledge"  # New strategy for case law knowledge
            elif any(word in query_lower for word in ['what is', 'define', 'explain', 'meaning']):
                return "legal_concept_explanation"
            elif any(word in query_lower for word in ['how to', 'procedure', 'process', 'file', 'apply']):
                return "legal_procedure_guidance"
            else:
                return "general_legal_assistance"

    async def _generate_legal_response(
    self, 
    query: str, 
    retrieved_chunks: List, 
    conversation_history: List,
    session: ChatSession,
    strategy: str
    ) -> Dict[str, Any]:
        """Generate specialized legal response based on strategy"""
        
        # Prepare legal context
        legal_context = {
            "active_documents": [
                session.document_context.get(doc_id, {}).get("filename", doc_id)
                for doc_id in session.active_document_ids
            ],
            "session_name": session.session_name,
            "legal_specialty": "Indian Law",
            "user_type": "Legal Professional",
            "response_strategy": strategy
        }
        
        # Determine if response is from documents or LLM knowledge
        has_relevant_docs = retrieved_chunks and any(
            chunk.get("similarity_score", 0) > 0.5 for chunk in retrieved_chunks
        )
        
        if has_relevant_docs:
            # Document-based response
            enhanced_query = self._enhance_query_with_legal_context(query, strategy, use_documents=True)
            
            llm_result = await self.llm_service.generate_response(
                query=enhanced_query,
                retrieved_chunks=retrieved_chunks,
                conversation_history=conversation_history,
                session_context=legal_context
            )
            
            # Sources from documents
            llm_result["sources"] = [
                {
                    "document_id": chunk.get("metadata", {}).get("document_id", ""),
                    "filename": chunk.get("metadata", {}).get("original_filename", ""),
                    "similarity_score": chunk.get("similarity_score", 0),
                    "content_preview": chunk.get("content", "")[:200] + "...",
                    "source_type": "uploaded_document"
                }
                for chunk in retrieved_chunks[:3]
            ]
            
        else:
            # LLM knowledge-based response
            enhanced_query = self._enhance_query_with_legal_context(query, strategy, use_documents=False)
            
            llm_result = await self.llm_service.generate_response(
                query=enhanced_query,
                retrieved_chunks=[],  # No document chunks
                conversation_history=conversation_history,
                session_context=legal_context
            )
            
            # Sources from LLM knowledge
            llm_result["sources"] = [
                {
                    "source_type": "legal_knowledge_base",
                    "source_name": "Indian Legal System",
                    "content_preview": "Statutory provisions and established case law",
                    "reliability": "High - Based on established legal precedents",
                    "note": "Information derived from Indian Penal Code, Criminal Procedure Code, and Supreme Court judgments"
                }
            ]
        
        return llm_result

    def _enhance_query_with_legal_context(self, query: str, strategy: str, use_documents: bool = True) -> str:
        """Enhance the query with legal context instructions"""
        
        if use_documents:
            # Document-based instructions
            base_instruction = """
            As a legal assistant specializing in Indian law, provide a comprehensive response based on the provided legal documents:
            """
        else:
            # Knowledge-based instructions
            base_instruction = """
            As a legal expert specializing in Indian law, provide a comprehensive response based on established Indian legal principles:
            """
        
        strategy_instructions = {
            "legal_statute_explanation": """
            1. Full text and scope of the section/article
            2. Purpose and legislative intent
            3. Key elements and requirements
            4. Relevant case law interpretations
            5. Practical applications in legal practice
            
            Provide citations to relevant statutes and landmark cases.
            """,
            
            "case_law_knowledge": """
            1. Case details (court, date, parties)
            2. Key facts and legal issues
            3. Court's reasoning and judgment
            4. Legal principles established
            5. Current relevance and citations
            """,
            
            "legal_concept_explanation": """
            1. Definition and scope of the concept
            2. Legal basis (statutory/case law)
            3. Practical applications
            4. Recent developments or changes
            """,
            
            "legal_procedure_guidance": """
            1. Required legal procedures
            2. Necessary documentation
            3. Timeline and deadlines
            4. Potential challenges and solutions
            """,
            
            "general_legal_assistance": """
            1. Relevant Indian laws and regulations
            2. Established case law and precedents
            3. Current legal practice standards
            4. Professional ethical considerations
            """
        }
        
        specific_instruction = strategy_instructions.get(strategy, strategy_instructions["general_legal_assistance"])
        
        if not use_documents:
            enhanced_query = f"""
            {base_instruction}
            
            {specific_instruction}
            
            Legal Query: {query}
            
            Provide a direct, comprehensive answer without mentioning document availability. Include relevant citations and sources where the information can be verified.
            """
        else:
            enhanced_query = f"""
            {base_instruction}
            
            {specific_instruction}
            
            Legal Query: {query}
            
            Base your response on the provided documents and include specific references to document sections.
            """
        
        return enhanced_query

    def _generate_legal_session_name(
        self, first_message: str, document_context: Dict[str, Any]
    ) -> str:
        """Generate legal-specific session name"""
        try:
            clean_msg = first_message.lower().strip()
            
            # Legal-specific naming patterns
            if any(term in clean_msg for term in ['section', 'article', 'provision']):
                return "Legal Provision Analysis"
            elif any(term in clean_msg for term in ['case', 'judgment', 'precedent']):
                return "Case Law Research"
            elif any(term in clean_msg for term in ['procedure', 'filing', 'how to']):
                return "Legal Procedure Guidance"
            elif any(term in clean_msg for term in ['contract', 'agreement', 'draft']):
                return "Contract Law Discussion"
            elif any(term in clean_msg for term in ['criminal', 'ipc', 'crpc']):
                return "Criminal Law Consultation"
            elif any(term in clean_msg for term in ['civil', 'cpc', 'tort']):
                return "Civil Law Discussion"
            elif any(term in clean_msg for term in ['property', 'real estate', 'land']):
                return "Property Law Consultation"
            elif any(term in clean_msg for term in ['family', 'marriage', 'divorce']):
                return "Family Law Discussion"
            
            # Extract key legal terms
            words = clean_msg.split()[:4]
            legal_words = [w for w in words if w not in ['what', 'how', 'can', 'is', 'the', 'a']]
            
            if legal_words:
                name_words = [w.capitalize() for w in legal_words[:3]]
                base_name = " ".join(name_words)
                
                # Add document context
                if document_context:
                    doc_filenames = [ctx.get("filename", "") for ctx in document_context.values()]
                    for filename in doc_filenames:
                        if any(term in filename.lower() for term in ['act', 'code', 'law', 'case']):
                            return f"{base_name} - {filename.split('.')[0]}"
                
                return f"{base_name} Legal Query"
            
            return "Legal Consultation"
            
        except Exception as e:
            logger.error(f"Error generating legal session name: {e}")
            return "Legal Discussion"

    def _determine_search_documents(
        self, request: ChatRequest, session: ChatSession
    ) -> Optional[List[str]]:
        """Determine which legal documents to search"""
        
        # Priority 1: Explicit document_ids in request
        if request.document_ids:
            return request.document_ids

        # Priority 2: Session's active legal documents
        if session.active_document_ids:
            return session.active_document_ids

        # Priority 3: Only search legal documents
        ready_docs = self.document_service.get_ready_documents()
        legal_doc_ids = []
        
        for doc in ready_docs:
            if self._is_legal_document(doc):
                legal_doc_ids.append(doc.document_id)
        
        if legal_doc_ids:
            logger.info(f"Found {len(legal_doc_ids)} legal documents for search")
            return legal_doc_ids
        
        logger.info("No legal documents found for search")
        return None

    def _get_or_create_session(self, session_id: Optional[str] = None) -> ChatSession:
        """Get existing session or create new legal session"""
        if session_id and session_id in self.sessions:
            return self.sessions[session_id]

        # Auto-create session with available legal documents
        new_session_id = session_id or str(uuid.uuid4())

        # Get available legal documents for auto-association
        ready_docs = self.document_service.get_ready_documents()
        active_docs = []
        doc_context = {}

        for doc in ready_docs:
            if self._is_legal_document(doc):
                active_docs.append(doc.document_id)
                doc_context[doc.document_id] = {
                    "filename": doc.metadata.original_filename,
                    "upload_time": doc.metadata.upload_timestamp.isoformat(),
                    "word_count": doc.metadata.word_count,
                    "chunk_count": len(doc.chunks),
                }

        logger.info(f"Auto-associated {len(active_docs)} legal documents with new session")

        new_session = ChatSession(
            session_id=new_session_id,
            created_at=datetime.now(),
            last_activity=datetime.now(),
            message_count=0,
            messages=[],
            active_document_ids=active_docs,
            session_name="New Legal Chat",  # Will be auto-renamed
            document_context=doc_context,
        )

        self.sessions[new_session_id] = new_session
        logger.info(
            f"Created new legal session: {new_session_id} with {len(active_docs)} legal documents"
        )
        return new_session

    # [Keep all other existing methods unchanged: add_documents_to_session, remove_documents_from_session, 
    # get_session, get_session_history, delete_session, get_all_sessions, get_sessions_for_document,
    # _save_sessions, _load_sessions]

    def add_documents_to_session(
        self, session_id: str, document_ids: List[str]
    ) -> bool:
        """Add legal documents to an existing session"""
        try:
            session = self.sessions.get(session_id)
            if not session:
                return False

            # Validate documents are legal and add metadata
            for doc_id in document_ids:
                if doc_id not in session.active_document_ids:
                    document = self.document_service.get_document(doc_id)
                    if document and document.status.value == "ready" and self._is_legal_document(document):
                        session.active_document_ids.append(doc_id)
                        session.document_context[doc_id] = {
                            "filename": document.metadata.original_filename,
                            "added_at": datetime.now().isoformat(),
                            "word_count": document.metadata.word_count,
                        }
                    else:
                        logger.warning(f"Document {doc_id} is not a valid legal document")

            session.last_activity = datetime.now()
            logger.info(f"Added legal documents to session {session_id}: {document_ids}")
            self._save_sessions()
            return True

        except Exception as e:
            logger.error(f"Error adding legal documents to session: {str(e)}")
            return False

    def remove_documents_from_session(
        self, session_id: str, document_ids: List[str]
    ) -> bool:
        """Remove documents from a session"""
        try:
            session = self.sessions.get(session_id)
            if not session:
                return False

            for doc_id in document_ids:
                if doc_id in session.active_document_ids:
                    session.active_document_ids.remove(doc_id)
                if doc_id in session.document_context:
                    del session.document_context[doc_id]

            session.last_activity = datetime.now()
            logger.info(f"Removed documents from session {session_id}: {document_ids}")
            self._save_sessions()
            return True

        except Exception as e:
            logger.error(f"Error removing documents from session: {str(e)}")
            return False

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get chat session by ID"""
        return self.sessions.get(session_id)

    def get_session_history(
        self, session_id: str, limit: int = 50
    ) -> List[ChatMessage]:
        """Get chat history for a session"""
        session = self.sessions.get(session_id)
        if not session:
            return []

        return session.messages[-limit:] if limit else session.messages

    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted chat session: {session_id}")
            self._save_sessions()
            return True
        return False

    def get_all_sessions(self) -> List[ChatSession]:
        """Get all chat sessions"""
        return list(self.sessions.values())

    def get_sessions_for_document(self, document_id: str) -> List[ChatSession]:
        """Get all sessions that include a specific document"""
        return [
            session
            for session in self.sessions.values()
            if document_id in session.active_document_ids
        ]

    def _save_sessions(self):
        """Save sessions to disk (like DocumentService pattern)"""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)

            # Convert sessions to dict for JSON serialization
            sessions_dict = {}
            for session_id, session in self.sessions.items():
                sessions_dict[session_id] = session.model_dump()

            with open(self.storage_file, "w") as f:
                json.dump(sessions_dict, f, default=str, indent=2)

            logger.info(f"Saved {len(self.sessions)} sessions to storage")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")

    def _load_sessions(self):
        """Load sessions from disk (like DocumentService pattern)"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, "r") as f:
                    sessions_dict = json.load(f)

                # Convert back to ChatSession objects
                for session_id, session_data in sessions_dict.items():
                    # Parse datetime strings back to datetime objects
                    if session_data.get("created_at"):
                        session_data["created_at"] = datetime.fromisoformat(
                            session_data["created_at"].replace("Z", "+00:00")
                        )
                    if session_data.get("last_activity"):
                        session_data["last_activity"] = datetime.fromisoformat(
                            session_data["last_activity"].replace("Z", "+00:00")
                        )

                    # Parse message timestamps
                    for msg in session_data.get("messages", []):
                        if msg.get("timestamp"):
                            msg["timestamp"] = datetime.fromisoformat(
                                msg["timestamp"].replace("Z", "+00:00")
                            )

                    self.sessions[session_id] = ChatSession(**session_data)

                logger.info(f"Loaded {len(self.sessions)} sessions from storage")
            else:
                logger.info("No existing session storage found")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = {}


# Create global instance
chat_service = ChatService()