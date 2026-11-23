"""
Conversation-level semantic encoding.

Captures speech acts, topic evolution, and goal tracking.
Enhanced with gestalt emergence and meta-cognitive markers.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Union
from enum import Enum
import torch
import re
import hashlib

# Import from the sibling module - using relative imports as in the spec
# Note: In actual usage, circular imports might be tricky if not careful,
# but ParagraphEncoder imports SentenceEncoder, and ConversationEncoder imports ParagraphEncoder,
# so the dependency chain is linear: Conv -> Para -> Sent.
from .paragraph_encoder import ParagraphEncoder, ParagraphEncoding
from .sentence_encoder import SentenceEncoder

class SpeechAct(Enum):
    """Speech act categories."""
    QUESTION = "question"
    ANSWER = "answer"
    REQUEST = "request"
    COMMAND = "command"
    ASSERTION = "assertion"
    ACKNOWLEDGMENT = "acknowledgment"
    CLARIFICATION = "clarification"
    ELABORATION = "elaboration"
    CORRECTION = "correction"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    META_REFLECTION = "meta_reflection"  # NEW: Thinking about thinking
    GESTALT_EXPRESSION = "gestalt_expression"  # NEW: Expressing pre-verbal insight
    ANALOGY_CONSTRUCTION = "analogy_construction"  # NEW: Building semantic shortcut


class ConversationGoal(Enum):
    """Conversation-level goals."""
    INFORMATION_SEEKING = "information_seeking"
    TASK_COMPLETION = "task_completion"
    PROBLEM_SOLVING = "problem_solving"
    BRAINSTORMING = "brainstorming"
    CLARIFICATION = "clarification"
    SOCIAL = "social"
    META_EXPLORATION = "meta_exploration"  # NEW: Understanding understanding
    GESTALT_ARTICULATION = "gestalt_articulation"  # NEW: Making pre-verbal verbal


class TopicShift(Enum):
    """Types of topic transitions."""
    CONTINUATION = "continuation"
    DRIFT = "drift"
    PIVOT = "pivot"
    RETURN = "return"
    DEEPENING = "deepening"
    BROADENING = "broadening"
    META_SHIFT = "meta_shift"  # NEW: Shift to meta-level


@dataclass
class TurnStructure:
    """Structure of a single turn."""
    speaker: str
    content: str
    speech_act: SpeechAct
    paragraph_encoding: Optional[ParagraphEncoding]
    topic_keywords: List[str]
    
    # Enhanced features
    has_gestalt_expression: bool = False
    has_meta_reflection: bool = False
    intensity_score: float = 0.5


@dataclass
class ConversationStructure:
    """Parsed conversation structure."""
    turns: List[TurnStructure]
    topic_evolution: List[Tuple[int, int, TopicShift]]
    goal: ConversationGoal
    resolution_status: str  # "resolved", "partial", "unresolved", "ongoing"
    
    # Enhanced features
    gestalt_emergence_points: List[int] = field(default_factory=list)  # Turn indices
    meta_reflection_points: List[int] = field(default_factory=list)
    intensity_arc: List[float] = field(default_factory=list)


@dataclass
class ConversationEncoding:
    """Result of conversation encoding."""
    vector: torch.Tensor
    structure: ConversationStructure
    turn_vectors: List[torch.Tensor]


class ConversationEncoder:
    """
    Encode conversations preserving interaction dynamics.
    Enhanced for cognitive pattern matching.
    """
    
    # Speech act markers
    SPEECH_ACT_MARKERS = {
        SpeechAct.QUESTION: ["?", "what", "how", "why", "when", "where", "who", "can you"],
        SpeechAct.REQUEST: ["please", "could you", "would you", "can you", "i need"],
        SpeechAct.COMMAND: ["do", "make", "create", "build", "write", "implement"],
        SpeechAct.ACKNOWLEDGMENT: ["ok", "thanks", "got it", "i see", "understood", "right"],
        SpeechAct.CLARIFICATION: ["you mean", "so basically", "in other words", "to clarify"],
        SpeechAct.AGREEMENT: ["yes", "exactly", "precisely", "correct", "absolutely"],
        SpeechAct.DISAGREEMENT: ["no", "but", "however", "actually", "not quite"],
        SpeechAct.META_REFLECTION: [
            "i'm trying to", "what i mean is", "the thing is",
            "it's hard to explain", "i'm realizing", "thinking about this",
            "thinking about", "i think about"
        ],
        SpeechAct.GESTALT_EXPRESSION: [
            "it's like", "there's this", "i can feel", "i just know",
            "something about", "the shape of", "hard to articulate"
        ],
        SpeechAct.ANALOGY_CONSTRUCTION: [
            "think of it like", "similar to", "just as", "imagine",
            "it's the same as", "reminds me of"
        ],
    }
    
    # Goal detection patterns
    GOAL_PATTERNS = {
        ConversationGoal.INFORMATION_SEEKING: r"(what|how|why|explain|tell me|describe)",
        ConversationGoal.TASK_COMPLETION: r"(create|build|write|implement|make|do|fix)",
        ConversationGoal.PROBLEM_SOLVING: r"(solve|figure out|debug|fix|resolve|work out)",
        ConversationGoal.BRAINSTORMING: r"(ideas|options|possibilities|explore|think about)",
        ConversationGoal.CLARIFICATION: r"(clarify|understand|mean|confused|unclear)",
        ConversationGoal.META_EXPLORATION: r"(how (i|we) think|understanding|pattern|insight)",
        ConversationGoal.GESTALT_ARTICULATION: r"(hard to explain|put into words|articulate|express)",
    }
    
    # Resolution markers
    RESOLUTION_MARKERS = {
        "resolved": ["thanks", "perfect", "that worked", "got it", "exactly what i needed"],
        "partial": ["mostly", "kind of", "somewhat", "partially"],
        "unresolved": ["still confused", "doesn't work", "not quite", "help more"],
    }
    
    def __init__(
        self,
        paragraph_encoder: ParagraphEncoder,
        dim: int = 8192,
        seed: int = 42
    ):
        self.para_encoder = paragraph_encoder
        self.dim = dim
        self.seed = seed
        self._role_vectors = {}
    
    def encode(self, turns: List[Dict[str, str]]) -> ConversationEncoding:
        """
        Encode a conversation.
        
        Args:
            turns: List of {"speaker": str, "content": str} dicts
        
        Returns:
            ConversationEncoding
        """
        if not turns:
            return ConversationEncoding(
                vector=torch.zeros(self.dim),
                structure=ConversationStructure(
                    turns=[],
                    topic_evolution=[],
                    goal=ConversationGoal.INFORMATION_SEEKING,
                    resolution_status="unresolved"
                ),
                turn_vectors=[]
            )
        
        # Parse each turn
        turn_structures = []
        turn_vectors = []
        
        for turn in turns:
            speaker = turn.get("speaker", "unknown")
            content = turn.get("content", "")
            
            # Encode paragraph
            para_enc = self.para_encoder.encode(content)
            
            # Detect speech act
            speech_act = self._detect_speech_act(content)
            
            # Extract topic keywords
            keywords = self._extract_keywords(para_enc)
            
            # Check for gestalt/meta markers
            has_gestalt = self._has_gestalt_expression(content)
            has_meta = self._has_meta_reflection(content)
            
            # Get intensity from paragraph
            intensity = 0.5
            if para_enc.structure.intensity_trajectory:
                vals = para_enc.structure.intensity_trajectory.values
                if vals:
                    intensity = max(vals)
            
            turn_struct = TurnStructure(
                speaker=speaker,
                content=content,
                speech_act=speech_act,
                paragraph_encoding=para_enc,
                topic_keywords=keywords,
                has_gestalt_expression=has_gestalt,
                has_meta_reflection=has_meta,
                intensity_score=intensity
            )
            
            turn_structures.append(turn_struct)
            turn_vectors.append(para_enc.vector)
        
        # Detect topic evolution
        topic_evolution = self._track_topic_evolution(turn_structures)
        
        # Detect conversation goal
        goal = self._detect_goal(turns)
        
        # Detect resolution status
        resolution = self._detect_resolution(turns, goal)
        
        # Find gestalt emergence points (NEW)
        gestalt_points = [i for i, t in enumerate(turn_structures) if t.has_gestalt_expression]
        
        # Find meta reflection points (NEW)
        meta_points = [i for i, t in enumerate(turn_structures) if t.has_meta_reflection]
        
        # Build intensity arc (NEW)
        intensity_arc = [t.intensity_score for t in turn_structures]
        
        # Build conversation vector
        conv_vec = self._build_conversation_vector(
            turn_vectors, turn_structures, goal, resolution,
            gestalt_points, meta_points
        )
        
        structure = ConversationStructure(
            turns=turn_structures,
            topic_evolution=topic_evolution,
            goal=goal,
            resolution_status=resolution,
            gestalt_emergence_points=gestalt_points,
            meta_reflection_points=meta_points,
            intensity_arc=intensity_arc
        )
        
        return ConversationEncoding(
            vector=conv_vec,
            structure=structure,
            turn_vectors=turn_vectors
        )
    
    def _detect_speech_act(self, content: str) -> SpeechAct:
        """Detect the speech act of a turn."""
        content_lower = content.lower().strip()
        
        # Check special acts first
        for act in [SpeechAct.META_REFLECTION, SpeechAct.GESTALT_EXPRESSION, 
                    SpeechAct.ANALOGY_CONSTRUCTION]:
            markers = self.SPEECH_ACT_MARKERS.get(act, [])
            if any(m in content_lower for m in markers):
                return act
        
        # Check question
        if content.strip().endswith("?"):
            return SpeechAct.QUESTION
        
        # Check other markers
        for act, markers in self.SPEECH_ACT_MARKERS.items():
            for marker in markers:
                if content_lower.startswith(marker) or f" {marker}" in content_lower[:50]:
                    return act
        
        return SpeechAct.ASSERTION
    
    def _extract_keywords(self, para_enc: ParagraphEncoding) -> List[str]:
        """Extract topic keywords from paragraph encoding."""
        keywords = []
        
        # Get from topic chain
        keywords.extend(para_enc.structure.topic_chain)
        
        # Get from named entities
        for enc in para_enc.structure.sentence_encodings:
            for entity, label in enc.structure.named_entities:
                if label in ["ORG", "PERSON", "GPE", "PRODUCT"]:
                    keywords.append(entity.lower())
        
        return list(set(keywords))
    
    def _has_gestalt_expression(self, content: str) -> bool:
        """Check if content contains gestalt expression."""
        content_lower = content.lower()
        markers = self.SPEECH_ACT_MARKERS.get(SpeechAct.GESTALT_EXPRESSION, [])
        return any(m in content_lower for m in markers)
    
    def _has_meta_reflection(self, content: str) -> bool:
        """Check if content contains meta-reflection."""
        content_lower = content.lower()
        markers = self.SPEECH_ACT_MARKERS.get(SpeechAct.META_REFLECTION, [])
        return any(m in content_lower for m in markers)
    
    def _track_topic_evolution(
        self, 
        turns: List[TurnStructure]
    ) -> List[Tuple[int, int, TopicShift]]:
        """Track how topics evolve across turns."""
        evolution = []
        
        for i in range(len(turns) - 1):
            j = i + 1
            keywords_i = set(turns[i].topic_keywords)
            keywords_j = set(turns[j].topic_keywords)
            
            # Check for meta shift
            if turns[j].has_meta_reflection and not turns[i].has_meta_reflection:
                evolution.append((i, j, TopicShift.META_SHIFT))
                continue
            
            if not keywords_i or not keywords_j:
                evolution.append((i, j, TopicShift.CONTINUATION))
                continue
            
            overlap = len(keywords_i & keywords_j)
            total = len(keywords_i | keywords_j)
            similarity = overlap / total if total > 0 else 0
            
            if similarity > 0.7:
                evolution.append((i, j, TopicShift.CONTINUATION))
            elif similarity > 0.4:
                evolution.append((i, j, TopicShift.DRIFT))
            elif similarity > 0.1:
                evolution.append((i, j, TopicShift.PIVOT))
            else:
                # Check if returning to earlier topic
                for k in range(i):
                    if set(turns[k].topic_keywords) & keywords_j:
                        evolution.append((i, j, TopicShift.RETURN))
                        break
                else:
                    evolution.append((i, j, TopicShift.PIVOT))
        
        return evolution
    
    def _detect_goal(self, turns: List[Dict[str, str]]) -> ConversationGoal:
        """Detect the primary goal of the conversation."""
        if not turns:
            return ConversationGoal.INFORMATION_SEEKING
        
        # Check first few turns
        early_content = " ".join(t.get("content", "") for t in turns[:3]).lower()
        
        for goal, pattern in self.GOAL_PATTERNS.items():
            if re.search(pattern, early_content):
                return goal
        
        return ConversationGoal.INFORMATION_SEEKING
    
    def _detect_resolution(
        self, 
        turns: List[Dict[str, str]], 
        goal: ConversationGoal
    ) -> str:
        """Detect whether the conversation goal was resolved."""
        if len(turns) < 2:
            return "ongoing"
        
        # Check last few turns from user
        last_user_turns = [t for t in turns[-3:] if t.get("speaker") == "user"]
        if not last_user_turns:
            return "ongoing"
        
        last_content = last_user_turns[-1].get("content", "").lower()
        
        for status, markers in self.RESOLUTION_MARKERS.items():
            if any(m in last_content for m in markers):
                return status
        
        return "ongoing"
    
    def _get_role_vector(self, role: str) -> torch.Tensor:
        """Get or generate a role vector."""
        if role not in self._role_vectors:
            seed = int(hashlib.md5(f"{self.seed}_{role}".encode()).hexdigest()[:8], 16)
            torch.manual_seed(seed)
            vec = torch.zeros(self.dim)
            rand = torch.rand(self.dim)
            vec[rand < 0.33] = 1.0
            vec[rand > 0.67] = -1.0
            self._role_vectors[role] = vec
        return self._role_vectors[role]
    
    def _build_conversation_vector(
        self,
        turn_vectors: List[torch.Tensor],
        turn_structures: List[TurnStructure],
        goal: ConversationGoal,
        resolution: str,
        gestalt_points: List[int],
        meta_points: List[int]
    ) -> torch.Tensor:
        """Build the conversation-level vector."""
        if not turn_vectors:
            return torch.zeros(self.dim)
        
        components = []
        
        # Add goal vector
        goal_vec = self._get_role_vector(f"GOAL_{goal.value}")
        components.append(goal_vec)
        
        # Add resolution vector
        resolution_vec = self._get_role_vector(f"RESOLUTION_{resolution}")
        components.append(resolution_vec)
        
        # Add gestalt emergence points with high weight (NEW)
        for idx in gestalt_points:
            components.append(turn_vectors[idx] * 2.0)
        
        # Add meta-reflection points (NEW)
        for idx in meta_points:
            meta_marker = self._get_role_vector("META_REFLECTION")
            bound = turn_vectors[idx] * meta_marker
            components.append(bound * 1.5)
        
        # Add turn vectors with speech act binding
        for i, (vec, struct) in enumerate(zip(turn_vectors, turn_structures)):
            act_vec = self._get_role_vector(f"ACT_{struct.speech_act.value}")
            bound = vec * act_vec
            
            # Weight by position (first and last turns matter more)
            if i == 0 or i == len(turn_vectors) - 1:
                bound = bound * 1.5
            
            components.append(bound)
        
        return self._bundle(components)
    
    def _bundle(self, vecs: List[torch.Tensor]) -> torch.Tensor:
        """Bundle vectors with thresholding."""
        if not vecs:
            return torch.zeros(self.dim)
        
        summed = torch.stack(vecs).sum(dim=0)
        result = torch.zeros_like(summed)
        threshold = len(vecs) * 0.3
        result[summed > threshold] = 1.0
        result[summed < -threshold] = -1.0
        
        return result
    
    def similarity(self, enc1: ConversationEncoding, enc2: ConversationEncoding) -> float:
        """Compute cosine similarity between conversation encodings."""
        return torch.nn.functional.cosine_similarity(
            enc1.vector.unsqueeze(0),
            enc2.vector.unsqueeze(0)
        ).item()
