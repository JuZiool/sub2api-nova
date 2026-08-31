package service

import "strings"

func optionalTrimmedStringPtr(raw string) *string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return nil
	}
	return &trimmed
}

// coalesceRequestedReasoningEffort preserves an explicitly captured client
// value and keeps existing callers compatible by falling back to the effective
// value when no separate request value was available.
func coalesceRequestedReasoningEffort(requested, effective *string) *string {
	if trimmed := strings.TrimSpace(optionalStringValue(requested)); trimmed != "" {
		return &trimmed
	}
	if trimmed := strings.TrimSpace(optionalStringValue(effective)); trimmed != "" {
		return &trimmed
	}
	return nil
}

func forwardResultBillingModel(requestedModel, upstreamModel string) string {
	if trimmed := strings.TrimSpace(requestedModel); trimmed != "" {
		return trimmed
	}
	return strings.TrimSpace(upstreamModel)
}

func optionalInt64Ptr(v int64) *int64 {
	if v == 0 {
		return nil
	}
	return &v
}
