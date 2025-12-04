"""Sistema de memoria y aprendizaje para el chatbot usando MySQL."""
import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import pymysql
from pymysql.cursors import DictCursor


class LearningMemory:
    """
    Sistema de memoria que aprende de las interacciones.
    Guarda preguntas y respuestas en MySQL para mejorar respuestas futuras.
    """
    
    # Palabras comunes que no deben influir en la similitud
    STOP_WORDS = {
        'que', 'es', 'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'al',
        'en', 'por', 'para', 'con', 'sin', 'sobre', 'entre', 'como', 'cual',
        'donde', 'cuando', 'quien', 'cuanto', 'me', 'te', 'se', 'nos', 'les',
        'lo', 'le', 'y', 'o', 'a', 'e', 'u', 'pero', 'si', 'no', 'mas', 'muy',
        'tan', 'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas',
        'aquel', 'aquella', 'su', 'sus', 'mi', 'tu', 'ser', 'estar', 'tiene',
        'significa', 'significa', 'quiere', 'decir', 'dame', 'dime', 'mostrar'
    }
    
    # Siglas y términos importantes que deben coincidir exactamente
    KEY_TERMS = {
        'ipc', 'eph', 'ecv', 'emae', 'sipa', 'oede', 'ripte', 'pbg', 'ipi',
        'dolar', 'blue', 'mep', 'ccl', 'oficial', 'censo', 'canasta', 'basica',
        'empleo', 'desempleo', 'inflacion', 'precios', 'salario', 'semaforo'
    }
    
    # SQL para crear la tabla si no existe
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS chatbot_learned_responses (
        id INT AUTO_INCREMENT PRIMARY KEY,
        question_key VARCHAR(100) NOT NULL,
        question TEXT NOT NULL,
        normalized_question VARCHAR(500) NOT NULL,
        response MEDIUMTEXT NOT NULL,
        category VARCHAR(100),
        is_conceptual BOOLEAN DEFAULT FALSE,
        quality_score FLOAT DEFAULT 0.8,
        use_count INT DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_used DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_question_key (question_key),
        INDEX idx_normalized (normalized_question(255)),
        INDEX idx_category (category),
        INDEX idx_use_count (use_count DESC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str = "chatbot_memory"):
        self.db_config = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'charset': 'utf8mb4',
            'cursorclass': DictCursor
        }
        self.database = database
        self.similarity_threshold = 0.80  # Aumentado para evitar falsos positivos
        self._ensure_database_and_table()
    
    def _get_connection(self, use_database: bool = True):
        """Obtiene una conexión a la base de datos."""
        config = self.db_config.copy()
        if use_database:
            config['database'] = self.database
        return pymysql.connect(**config)
    
    def _ensure_database_and_table(self) -> None:
        """Crea la base de datos y tabla si no existen."""
        try:
            # Crear base de datos si no existe
            conn = self._get_connection(use_database=False)
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            conn.close()
            
            # Crear tabla si no existe
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(self.CREATE_TABLE_SQL)
            conn.commit()
            conn.close()
            
            logging.info(f"Learning memory database '{self.database}' ready")
        except Exception as e:
            logging.error(f"Error initializing learning memory database: {e}")
            raise
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para comparación."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', 'ü': 'u'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text[:500]  # Limitar longitud para índice
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calcula similitud entre dos textos, priorizando términos clave."""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        # Extraer términos clave (siglas, términos importantes)
        key_words1 = words1 & self.KEY_TERMS
        key_words2 = words2 & self.KEY_TERMS
        
        # Si ambos tienen términos clave diferentes, NO son similares
        if key_words1 and key_words2 and key_words1 != key_words2:
            return 0.0  # ECV != EPH, IPC != dolar, etc.
        
        # Si uno tiene término clave y el otro no lo tiene, baja similitud
        if (key_words1 or key_words2) and key_words1 != key_words2:
            return 0.3
        
        # Remover stop words para comparación
        content_words1 = words1 - self.STOP_WORDS
        content_words2 = words2 - self.STOP_WORDS
        
        if not content_words1 or not content_words2:
            return SequenceMatcher(None, norm1, norm2).ratio() * 0.5
        
        # Similitud basada en palabras de contenido
        common_content = content_words1 & content_words2
        content_similarity = len(common_content) / max(len(content_words1), len(content_words2))
        
        # Similitud de secuencia (para frases similares)
        seq_similarity = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Bonus si los términos clave coinciden
        key_bonus = 0.3 if key_words1 and key_words1 == key_words2 else 0.0
        
        return min((content_similarity * 0.5) + (seq_similarity * 0.2) + key_bonus, 1.0)
    
    def _generate_key(self, question: str) -> str:
        """Genera una clave única para la pregunta."""
        normalized = self._normalize_text(question)
        words = [w for w in normalized.split() if len(w) > 2][:5]
        return '_'.join(words)[:100] if words else 'unknown'
    
    def find_similar(self, question: str, min_similarity: float = None) -> Optional[Tuple[int, Dict, float]]:
        """
        Busca una pregunta similar en la base de datos.
        
        Returns:
            Tupla (id, entry, similarity) o None si no encuentra
        """
        if min_similarity is None:
            min_similarity = self.similarity_threshold
        
        normalized = self._normalize_text(question)
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Buscar primero por coincidencia exacta normalizada
                cursor.execute(
                    "SELECT * FROM chatbot_learned_responses WHERE normalized_question = %s LIMIT 1",
                    (normalized,)
                )
                exact_match = cursor.fetchone()
                if exact_match:
                    conn.close()
                    return (exact_match['id'], exact_match, 1.0)
                
                # Buscar candidatos con palabras similares
                words = normalized.split()[:3]
                if not words:
                    conn.close()
                    return None
                
                # Construir búsqueda por palabras clave
                like_conditions = " OR ".join(["normalized_question LIKE %s" for _ in words])
                like_values = [f"%{w}%" for w in words]
                
                cursor.execute(
                    f"SELECT * FROM chatbot_learned_responses WHERE {like_conditions} ORDER BY use_count DESC LIMIT 50",
                    like_values
                )
                candidates = cursor.fetchall()
            conn.close()
            
            # Calcular similitud para cada candidato
            best_match = None
            best_similarity = 0.0
            
            for candidate in candidates:
                similarity = self._calculate_similarity(question, candidate['question'])
                if similarity > best_similarity and similarity >= min_similarity:
                    best_similarity = similarity
                    best_match = (candidate['id'], candidate, similarity)
            
            if best_match:
                logging.info(f"Found similar question with {best_match[2]:.2%} similarity")
            
            return best_match
            
        except Exception as e:
            logging.error(f"Error finding similar question: {e}")
            return None
    
    def learn(self, question: str, response: str, category: str = None,
              is_conceptual: bool = False, quality_score: float = 0.8) -> Optional[int]:
        """
        Aprende de una nueva interacción.
        
        Returns:
            ID de la entrada guardada o None si falla
        """
        question_key = self._generate_key(question)
        normalized = self._normalize_text(question)
        
        try:
            # Verificar si ya existe una entrada muy similar
            existing = self.find_similar(question, min_similarity=0.9)
            
            conn = self._get_connection()
            with conn.cursor() as cursor:
                if existing:
                    # Actualizar entrada existente
                    entry_id = existing[0]
                    old_score = existing[1].get('quality_score', 0)
                    
                    if quality_score > old_score:
                        # Actualizar respuesta si es de mejor calidad
                        cursor.execute("""
                            UPDATE chatbot_learned_responses 
                            SET response = %s, quality_score = %s, use_count = use_count + 1
                            WHERE id = %s
                        """, (response, quality_score, entry_id))
                    else:
                        # Solo incrementar contador
                        cursor.execute(
                            "UPDATE chatbot_learned_responses SET use_count = use_count + 1 WHERE id = %s",
                            (entry_id,)
                        )
                    conn.commit()
                    conn.close()
                    logging.info(f"Updated existing entry: {question_key} (id={entry_id})")
                    return entry_id
                else:
                    # Nueva entrada
                    cursor.execute("""
                        INSERT INTO chatbot_learned_responses 
                        (question_key, question, normalized_question, response, category, is_conceptual, quality_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (question_key, question, normalized, response, category, is_conceptual, quality_score))
                    conn.commit()
                    entry_id = cursor.lastrowid
                    conn.close()
                    logging.info(f"Learned new entry: {question_key} (id={entry_id})")
                    return entry_id
                    
        except Exception as e:
            logging.error(f"Error learning: {e}")
            return None
    
    def get_response(self, question: str) -> Optional[str]:
        """
        Obtiene una respuesta aprendida si existe.
        
        Returns:
            Respuesta si encuentra una similar, None si no
        """
        match = self.find_similar(question)
        if match:
            entry_id, entry, similarity = match
            
            # Actualizar uso
            try:
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE chatbot_learned_responses SET use_count = use_count + 1 WHERE id = %s",
                        (entry_id,)
                    )
                conn.commit()
                conn.close()
            except Exception as e:
                logging.warning(f"Could not update use count: {e}")
            
            return entry.get('response')
        return None
    
    def get_suggestions(self, partial_text: str, limit: int = 5) -> List[str]:
        """Obtiene sugerencias basadas en texto parcial."""
        if not partial_text or len(partial_text) < 2:
            return []
        
        normalized = self._normalize_text(partial_text)
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT question FROM chatbot_learned_responses 
                    WHERE normalized_question LIKE %s 
                    ORDER BY use_count DESC 
                    LIMIT %s
                """, (f"%{normalized}%", limit))
                results = cursor.fetchall()
            conn.close()
            
            return [r['question'] for r in results]
        except Exception as e:
            logging.error(f"Error getting suggestions: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas de la memoria."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as total FROM chatbot_learned_responses")
                total = cursor.fetchone()['total']
                
                cursor.execute("SELECT COUNT(*) as count FROM chatbot_learned_responses WHERE is_conceptual = TRUE")
                conceptual = cursor.fetchone()['count']
                
                cursor.execute("SELECT category, COUNT(*) as count FROM chatbot_learned_responses GROUP BY category")
                categories = {r['category'] or 'unknown': r['count'] for r in cursor.fetchall()}
                
                cursor.execute("SELECT SUM(use_count) as total_uses FROM chatbot_learned_responses")
                total_uses = cursor.fetchone()['total_uses'] or 0
                
                cursor.execute("""
                    SELECT question, use_count FROM chatbot_learned_responses 
                    ORDER BY use_count DESC LIMIT 5
                """)
                top_questions = [{'question': r['question'], 'uses': r['use_count']} for r in cursor.fetchall()]
                
            conn.close()
            
            return {
                'total_entries': total,
                'conceptual_questions': conceptual,
                'data_questions': total - conceptual,
                'categories': categories,
                'total_uses': total_uses,
                'average_uses': total_uses / total if total > 0 else 0,
                'top_questions': top_questions
            }
        except Exception as e:
            logging.error(f"Error getting stats: {e}")
            return {'error': str(e)}
    
    def get_recent_entries(self, limit: int = 20) -> List[Dict]:
        """Obtiene las entradas más recientes."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, question_key, question, category, is_conceptual, 
                           use_count, quality_score, created_at, last_used
                    FROM chatbot_learned_responses 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """, (limit,))
                results = cursor.fetchall()
            conn.close()
            
            # Convertir datetime a string para JSON
            for r in results:
                if r.get('created_at'):
                    r['created_at'] = r['created_at'].isoformat()
                if r.get('last_used'):
                    r['last_used'] = r['last_used'].isoformat()
            
            return results
        except Exception as e:
            logging.error(f"Error getting recent entries: {e}")
            return []
    
    def export_for_training(self) -> List[Dict]:
        """Exporta datos para entrenamiento de modelo."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT question, response, category, quality_score 
                    FROM chatbot_learned_responses 
                    WHERE quality_score >= 0.7
                    ORDER BY use_count DESC
                """)
                results = cursor.fetchall()
            conn.close()
            return results
        except Exception as e:
            logging.error(f"Error exporting: {e}")
            return []


# Instancia global
_memory_instance: Optional[LearningMemory] = None


def get_learning_memory(host: str = None, port: int = None, 
                        user: str = None, password: str = None) -> Optional[LearningMemory]:
    """Obtiene la instancia global de memoria."""
    global _memory_instance
    
    if _memory_instance is None:
        if not all([host, port, user, password]):
            logging.warning("Database credentials required for learning memory")
            return None
        try:
            _memory_instance = LearningMemory(host, port, user, password)
        except Exception as e:
            logging.error(f"Could not initialize learning memory: {e}")
            return None
    
    return _memory_instance
