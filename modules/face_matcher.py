"""
Face Matching Module
Advanced distance metrics and matching strategies
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.spatial.distance import euclidean, mahalanobis
from scipy.stats import chi2


class FaceMatcher:
    """
    Face matching with multiple distance metrics
    """
    
    def __init__(self, 
                 primary_metric='cosine',
                 threshold=0.75,
                 margin_threshold=0.10,
                 use_ensemble=False):  # Changed to False - pure cosine is best for MobileFaceNet
        """
        Args:
            primary_metric: 'cosine' (recommended for InsightFace L2-normalized embeddings), 'euclidean', or 'ensemble'
            threshold: Similarity threshold for match
            margin_threshold: Minimum margin between top 2 matches
            use_ensemble: Use weighted combination of metrics (not recommended for normalized embeddings)
        """
        self.primary_metric = primary_metric
        self.threshold = threshold
        self.margin_threshold = margin_threshold
        self.use_ensemble = use_ensemble  # Pure cosine is optimal for InsightFace
    
    def compute_similarity(self, embedding1, embedding2, metric=None):
        """
        Compute similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            metric: Distance metric to use (overrides default)
            
        Returns:
            Similarity score (0-1, higher is more similar)
        """
        metric = metric or self.primary_metric
        
        if metric == 'cosine':
            return self._cosine_similarity(embedding1, embedding2)
        elif metric == 'euclidean':
            return self._euclidean_similarity(embedding1, embedding2)
        elif metric == 'mahalanobis':
            return self._mahalanobis_similarity(embedding1, embedding2)
        elif metric == 'ensemble':
            return self._ensemble_similarity(embedding1, embedding2)
        else:
            return self._cosine_similarity(embedding1, embedding2)
    
    def _cosine_similarity(self, emb1, emb2):
        """
        Cosine similarity - optimal for L2-normalized embeddings (InsightFace 512-D).
        For normalized vectors: cosine_sim = 1 - (euclidean_dist² / 2)
        """
        return cosine_similarity([emb1], [emb2])[0][0]
    
    def _euclidean_similarity(self, emb1, emb2):
        """
        Euclidean distance converted to similarity
        Distance in range [0, 2] for normalized vectors
        Similarity in range [0, 1]
        """
        distance = euclidean(emb1, emb2)
        similarity = 1.0 / (1.0 + distance)
        return similarity
    
    def _mahalanobis_similarity(self, emb1, emb2):
        """
        Mahalanobis distance (accounts for correlations)
        Requires covariance matrix - use identity as approximation
        """
        # Use identity matrix as covariance (simplification)
        # For proper Mahalanobis, need covariance from training data
        diff = emb1 - emb2
        distance = np.sqrt(np.sum(diff ** 2))  # Simplified
        similarity = 1.0 / (1.0 + distance)
        return similarity
    
    def _ensemble_similarity(self, emb1, emb2):
        """
        Weighted ensemble of multiple metrics
        """
        cosine = self._cosine_similarity(emb1, emb2)
        euclidean = self._euclidean_similarity(emb1, emb2)
        
        # Weighted average (cosine weighted higher)
        similarity = 0.7 * cosine + 0.3 * euclidean
        return similarity
    
    def match_face(self, query_embedding, database_embeddings, names):
        """
        Match query embedding against database using weighted averaged embedding approach.
        
        Algorithm:
        1. Compare with averaged embedding (60% weight) - more stable
        2. Compare with top-3 individual embeddings (40% weight) - handles variation
        3. Combined weighted score determines final match
        
        Args:
            query_embedding: Query face embedding
            database_embeddings: Dict of {name: person_data}
            names: List of names in database
            
        Returns:
            (best_match_name, similarity, is_confident)
        """
        if not database_embeddings:
            return "Unknown", 0.0, False
        
        # Compute similarities for all persons
        all_similarities = []
        
        for name in names:
            person_data = database_embeddings[name]
            
            # Handle both dict and legacy list formats
            if isinstance(person_data, dict):
                person_embeddings = person_data.get('individual', [])
                averaged_embedding = person_data.get('averaged', None)
            else:
                person_embeddings = person_data
                averaged_embedding = None
            
            if not person_embeddings:
                continue
            
            # === STEP 1: Averaged embedding similarity (60% weight) ===
            if averaged_embedding is not None:
                avg_sim = self.compute_similarity(query_embedding, averaged_embedding)
            else:
                # Fallback: compute average on the fly
                import numpy as np
                avg_emb = np.mean(person_embeddings, axis=0)
                avg_emb = avg_emb / (np.linalg.norm(avg_emb) + 1e-10)
                avg_sim = self.compute_similarity(query_embedding, avg_emb)
            
            # === STEP 2: Top-3 individual embeddings similarity (40% weight) ===
            individual_sims = []
            for stored_emb in person_embeddings:
                sim = self.compute_similarity(query_embedding, stored_emb)
                individual_sims.append(sim)
            
            # Get top-3 average from individuals
            top3_sims = sorted(individual_sims, reverse=True)[:3]
            top3_avg = sum(top3_sims) / len(top3_sims) if top3_sims else 0.0
            
            # === STEP 3: Combined weighted score ===
            # 60% averaged (stable) + 40% top-3 individual (handles variation)
            combined_sim = 0.6 * avg_sim + 0.4 * top3_avg
            
            all_similarities.append({
                'name': name,
                'similarity': combined_sim,
                'avg_sim': avg_sim,
                'top3_sim': top3_avg,
                'max_sim': max(individual_sims) if individual_sims else 0.0
            })
        
        # Sort by combined similarity
        all_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        if len(all_similarities) == 0:
            return "Unknown", 0.0, False
        
        best_match = all_similarities[0]
        best_name = best_match['name']
        best_similarity = best_match['similarity']
        
        # Check threshold
        if best_similarity < self.threshold:
            return "Unknown", best_similarity, False
        
        # Check margin (confidence in decision)
        if len(all_similarities) > 1:
            second_best = all_similarities[1]
            margin = best_similarity - second_best['similarity']
            
            if margin < self.margin_threshold:
                # Too close - not confident enough
                # Log for debugging
                # print(f"⚠️ Low margin: {best_name}={best_similarity:.3f} vs {second_best['name']}={second_best['similarity']:.3f} (margin={margin:.3f})")
                return "Unknown", best_similarity, False
        
        return best_name, best_similarity, True
    
    def verify_face(self, embedding1, embedding2):
        """
        1:1 verification
        
        Args:
            embedding1: First face embedding
            embedding2: Second face embedding
            
        Returns:
            (is_same_person: bool, similarity: float)
        """
        similarity = self.compute_similarity(embedding1, embedding2)
        is_same = similarity >= self.threshold
        
        return is_same, similarity
