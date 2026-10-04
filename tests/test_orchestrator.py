"""
Tests for orchestrator cascade processing and hierarchical pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from gse.patterns import (
    OrchestratedPipeline,
    OrchestratorNetwork,
    ScaleNetworkCollection,
)


@pytest.fixture(scope="module")
def orchestrator():
    networks = ScaleNetworkCollection()
    return OrchestratorNetwork(networks)


class TestSingleScaleProcess:
    def test_single_scale_route(self, orchestrator):
        """Without cascade, only one scale is engaged."""
        result = orchestrator.process(
            {
                "features": {"x": 0.5, "y": 0.3},
                "word": {"FEEL": 0.8},
            }
        )
        assert len(result["scales_used"]) == 1

    def test_force_scale(self, orchestrator):
        """force_scale should override routing."""
        result = orchestrator.process(
            {"sentence": {"SYN_SUBJ": 1.0}},
            force_scale="sentence",
        )
        assert result["scales_used"] == ["sentence"]


class TestCascadeProcess:
    def test_cascade_engages_all_scales(self, orchestrator):
        """cascade=True should run text → paragraph → sentence → word."""
        result = orchestrator.process(
            {
                "text": {"genre_NARRATIVE": 1.0},
                "paragraph": {"CAUSE": 0.5},
                "sentence": {"SYN_SUBJ": 1.0},
                "word": {"FEEL": 1.0},
            },
            cascade=True,
        )
        assert result["scales_used"] == ["text", "paragraph", "sentence", "word"]

    def test_cascade_outputs_per_scale(self, orchestrator):
        """cascade should produce an output entry per scale."""
        result = orchestrator.process(
            {
                "text": {"genre_NARRATIVE": 1.0},
                "paragraph": {"CAUSE": 0.5},
                "sentence": {"SYN_SUBJ": 1.0},
                "word": {"FEEL": 1.0},
            },
            cascade=True,
        )
        assert "text" in result["outputs"]
        assert "paragraph" in result["outputs"]
        assert "sentence" in result["outputs"]
        assert "word" in result["outputs"]

    def test_cascade_propagates_prior_features(self, orchestrator):
        """Each scale should see prior-scale activations as constraint features."""
        # Use valid network primitive names so text-scale produces a real activation
        r_with_text = orchestrator.process(
            {
                "text": {"NARRATIVE": 1.0, "FORMAL": 0.8},
                "paragraph": {"CAUSE": 0.5},
                "sentence": {"SYN_SUBJ": 1.0},
                "word": {"FEEL": 1.0},
            },
            cascade=True,
        )
        r_without_text = orchestrator.process(
            {
                "text": {},
                "paragraph": {"CAUSE": 0.5},
                "sentence": {"SYN_SUBJ": 1.0},
                "word": {"FEEL": 1.0},
            },
            cascade=True,
        )
        # When text-scale fires, its activation becomes prior_* features
        # for the paragraph network — confidences should differ between runs
        assert r_with_text["confidence"] != r_without_text["confidence"]


class TestHierarchicalPipeline:
    @pytest.fixture(scope="class")
    def pipeline(self):
        return OrchestratedPipeline()

    def test_process_hierarchical_basic(self, pipeline):
        text = "The cat sat on the mat. The dog barked loudly."
        result = pipeline.process_hierarchical(text)
        assert "paragraphs" in result
        assert "sentences" in result
        assert "cascade_context" in result
        assert "scales_used" in result

    def test_segmentation_single_paragraph(self, pipeline):
        text = "First sentence. Second sentence."
        result = pipeline.process_hierarchical(text)
        assert len(result["paragraphs"]) == 1
        assert len(result["sentences"][0]) == 2

    def test_segmentation_multiple_paragraphs(self, pipeline):
        text = "First paragraph. With two sentences.\n\nSecond paragraph here."
        result = pipeline.process_hierarchical(text)
        assert len(result["paragraphs"]) == 2
        assert len(result["sentences"][0]) == 2
        assert len(result["sentences"][1]) == 1

    def test_cascade_context_present(self, pipeline):
        text = "The cat sat on the mat."
        result = pipeline.process_hierarchical(text)
        context = result["cascade_context"]
        assert "genre" in context
        assert "register" in context
        assert "domain" in context

    def test_all_scales_used_in_hierarchical(self, pipeline):
        text = "The cat sat on the mat."
        result = pipeline.process_hierarchical(text)
        assert "text" in result["scales_used"]
        assert "paragraph" in result["scales_used"]
        assert "sentence" in result["scales_used"]
        assert "word" in result["scales_used"]

    def test_paragraph_features_per_paragraph(self, pipeline):
        text = "Para one here.\n\nPara two here."
        result = pipeline.process_hierarchical(text)
        assert len(result["paragraph_features"]) == 2


class TestBackwardCompatibility:
    def test_process_text_still_works(self):
        pipeline = OrchestratedPipeline()
        result = pipeline.process_text("The cat sat.", task="classify")
        assert "scales_used" in result
        assert "confidence" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
