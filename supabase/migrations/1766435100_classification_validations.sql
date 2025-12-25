-- Migration: classification_validations
-- Created at: 1766435100
-- Description: Add classification_validations table for ground truth labels and accuracy tracking
--
-- Purpose: Enable manual validation of AI-generated strategic pillar classifications
-- to achieve >85% classification accuracy target.

-- ============================================================================
-- Create classification_validations table
-- ============================================================================

CREATE TABLE IF NOT EXISTS classification_validations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Card reference
    card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,

    -- Classification data
    predicted_pillar TEXT NOT NULL,      -- AI-predicted pillar code (e.g., CH, MC)
    ground_truth_pillar TEXT NOT NULL,   -- Human-verified correct pillar code
    is_correct BOOLEAN NOT NULL GENERATED ALWAYS AS (predicted_pillar = ground_truth_pillar) STORED,

    -- Reviewer information
    reviewer_id UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,

    -- Additional metadata
    notes TEXT,                          -- Optional notes explaining the decision
    confidence_at_prediction FLOAT,      -- AI confidence score at time of prediction

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,

    -- Constraints
    CONSTRAINT valid_predicted_pillar CHECK (predicted_pillar ~ '^[A-Z]{2}$'),
    CONSTRAINT valid_ground_truth_pillar CHECK (ground_truth_pillar ~ '^[A-Z]{2}$'),
    CONSTRAINT confidence_range CHECK (confidence_at_prediction IS NULL OR (confidence_at_prediction >= 0 AND confidence_at_prediction <= 1))
);

-- ============================================================================
-- Create unique constraint to prevent duplicate validations
-- ============================================================================

-- Each card can only be validated once per reviewer
CREATE UNIQUE INDEX IF NOT EXISTS idx_classification_validations_card_reviewer
    ON classification_validations(card_id, reviewer_id);

-- ============================================================================
-- Create indexes for efficient queries
-- ============================================================================

-- Index for accuracy calculations (filtering by is_correct)
CREATE INDEX IF NOT EXISTS idx_classification_validations_is_correct
    ON classification_validations(is_correct);

-- Index for time-based queries (e.g., validations this week)
CREATE INDEX IF NOT EXISTS idx_classification_validations_created_at
    ON classification_validations(created_at DESC);

-- Index for pillar-specific accuracy analysis
CREATE INDEX IF NOT EXISTS idx_classification_validations_pillars
    ON classification_validations(predicted_pillar, ground_truth_pillar);

-- Index for reviewer activity tracking
CREATE INDEX IF NOT EXISTS idx_classification_validations_reviewer
    ON classification_validations(reviewer_id, created_at DESC);

-- ============================================================================
-- Enable Row Level Security
-- ============================================================================

ALTER TABLE classification_validations ENABLE ROW LEVEL SECURITY;

-- Users can view all validation records (for transparency and learning)
CREATE POLICY "Users can view all classification validations"
    ON classification_validations FOR SELECT
    USING (true);

-- Users can create validation records (for themselves as reviewer)
CREATE POLICY "Users can create classification validations"
    ON classification_validations FOR INSERT
    WITH CHECK (reviewer_id = auth.uid());

-- Users can update their own validation records
CREATE POLICY "Users can update own classification validations"
    ON classification_validations FOR UPDATE
    USING (reviewer_id = auth.uid());

-- Users can delete their own validation records
CREATE POLICY "Users can delete own classification validations"
    ON classification_validations FOR DELETE
    USING (reviewer_id = auth.uid());

-- Service role has full access (for backend processing)
CREATE POLICY "Service role full access on classification_validations"
    ON classification_validations FOR ALL
    USING (auth.role() = 'service_role');

-- ============================================================================
-- Create function to compute classification accuracy
-- ============================================================================

CREATE OR REPLACE FUNCTION compute_classification_accuracy(
    p_since TIMESTAMPTZ DEFAULT NULL,
    p_pillar TEXT DEFAULT NULL
)
RETURNS TABLE (
    total_validations BIGINT,
    correct_classifications BIGINT,
    accuracy_percentage NUMERIC(5,2),
    meets_target BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_validations,
        COUNT(*) FILTER (WHERE is_correct)::BIGINT as correct_classifications,
        CASE
            WHEN COUNT(*) > 0 THEN
                ROUND((COUNT(*) FILTER (WHERE is_correct)::NUMERIC / COUNT(*)::NUMERIC) * 100, 2)
            ELSE 0.00
        END as accuracy_percentage,
        CASE
            WHEN COUNT(*) > 0 THEN
                (COUNT(*) FILTER (WHERE is_correct)::NUMERIC / COUNT(*)::NUMERIC) > 0.85
            ELSE false
        END as meets_target
    FROM classification_validations
    WHERE
        (p_since IS NULL OR created_at >= p_since)
        AND (p_pillar IS NULL OR predicted_pillar = p_pillar OR ground_truth_pillar = p_pillar);
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION compute_classification_accuracy(TIMESTAMPTZ, TEXT) TO authenticated;

-- ============================================================================
-- Create function to get accuracy by pillar
-- ============================================================================

CREATE OR REPLACE FUNCTION get_accuracy_by_pillar(
    p_since TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
    pillar TEXT,
    total_validations BIGINT,
    correct_classifications BIGINT,
    accuracy_percentage NUMERIC(5,2)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT
        cv.ground_truth_pillar as pillar,
        COUNT(*)::BIGINT as total_validations,
        COUNT(*) FILTER (WHERE cv.is_correct)::BIGINT as correct_classifications,
        CASE
            WHEN COUNT(*) > 0 THEN
                ROUND((COUNT(*) FILTER (WHERE cv.is_correct)::NUMERIC / COUNT(*)::NUMERIC) * 100, 2)
            ELSE 0.00
        END as accuracy_percentage
    FROM classification_validations cv
    WHERE p_since IS NULL OR cv.created_at >= p_since
    GROUP BY cv.ground_truth_pillar
    ORDER BY cv.ground_truth_pillar;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_accuracy_by_pillar(TIMESTAMPTZ) TO authenticated;

-- ============================================================================
-- Create function to get confusion matrix
-- ============================================================================

CREATE OR REPLACE FUNCTION get_classification_confusion_matrix(
    p_since TIMESTAMPTZ DEFAULT NULL
)
RETURNS TABLE (
    predicted_pillar TEXT,
    actual_pillar TEXT,
    count BIGINT,
    percentage NUMERIC(5,2)
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_total BIGINT;
BEGIN
    -- Get total count first
    SELECT COUNT(*) INTO v_total
    FROM classification_validations
    WHERE p_since IS NULL OR created_at >= p_since;

    RETURN QUERY
    SELECT
        cv.predicted_pillar,
        cv.ground_truth_pillar as actual_pillar,
        COUNT(*)::BIGINT as count,
        CASE
            WHEN v_total > 0 THEN
                ROUND((COUNT(*)::NUMERIC / v_total::NUMERIC) * 100, 2)
            ELSE 0.00
        END as percentage
    FROM classification_validations cv
    WHERE p_since IS NULL OR cv.created_at >= p_since
    GROUP BY cv.predicted_pillar, cv.ground_truth_pillar
    ORDER BY count DESC;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION get_classification_confusion_matrix(TIMESTAMPTZ) TO authenticated;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE classification_validations IS 'Ground truth labels for validating AI classification accuracy. Used to achieve >85% accuracy target.';

COMMENT ON COLUMN classification_validations.card_id IS 'Reference to the card that was classified';
COMMENT ON COLUMN classification_validations.predicted_pillar IS 'The strategic pillar code predicted by AI (e.g., CH, MC, ES, GS, PS, CI)';
COMMENT ON COLUMN classification_validations.ground_truth_pillar IS 'The correct strategic pillar code as determined by human reviewer';
COMMENT ON COLUMN classification_validations.is_correct IS 'Computed column: true if predicted_pillar matches ground_truth_pillar';
COMMENT ON COLUMN classification_validations.reviewer_id IS 'User who submitted the ground truth validation';
COMMENT ON COLUMN classification_validations.notes IS 'Optional notes explaining the classification decision';
COMMENT ON COLUMN classification_validations.confidence_at_prediction IS 'AI confidence score (0-1) at time of original prediction';

COMMENT ON FUNCTION compute_classification_accuracy IS 'Computes overall classification accuracy metrics with optional time and pillar filters';
COMMENT ON FUNCTION get_accuracy_by_pillar IS 'Returns accuracy breakdown by strategic pillar';
COMMENT ON FUNCTION get_classification_confusion_matrix IS 'Returns confusion matrix showing prediction patterns';
