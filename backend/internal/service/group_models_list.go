package service

import "strings"

func normalizeGroupModelsListConfig(cfg GroupModelsListConfig) GroupModelsListConfig {
	out := GroupModelsListConfig{Enabled: cfg.Enabled}
	out.Models = normalizeGroupModelIDs(cfg.Models)
	out.HiddenModels = normalizeGroupModelIDs(cfg.HiddenModels)
	return out
}

func normalizeGroupModelIDs(models []string) []string {
	if len(models) == 0 {
		return nil
	}
	seen := make(map[string]struct{}, len(models))
	out := make([]string, 0, len(models))
	for _, model := range models {
		model = strings.TrimSpace(model)
		if model == "" {
			continue
		}
		if _, ok := seen[model]; ok {
			continue
		}
		seen[model] = struct{}{}
		out = append(out, model)
	}
	if len(out) == 0 {
		return nil
	}
	return out
}

func (g *Group) CustomModelsListEnabled() bool {
	return g != nil && g.ModelsListConfig.Enabled && len(g.ModelsListConfig.Models) > 0
}

// IsModelHidden reports whether a group-level model deny rule matches model.
// A trailing * is supported as a prefix wildcard for model families.
func (g *Group) IsModelHidden(model string) bool {
	if g == nil {
		return false
	}
	return isGroupModelHidden(g.ModelsListConfig.HiddenModels, model)
}

func isGroupModelHidden(patterns []string, model string) bool {
	model = strings.TrimSpace(model)
	if model == "" {
		return false
	}
	modelCandidates := []string{model}
	if strings.HasPrefix(model, "models/") {
		modelCandidates = append(modelCandidates, strings.TrimPrefix(model, "models/"))
	}
	for _, rawPattern := range patterns {
		pattern := strings.TrimSpace(rawPattern)
		if pattern == "" {
			continue
		}
		patternCandidates := []string{pattern}
		if strings.HasPrefix(pattern, "models/") {
			patternCandidates = append(patternCandidates, strings.TrimPrefix(pattern, "models/"))
		}
		for _, candidate := range modelCandidates {
			for _, candidatePattern := range patternCandidates {
				if candidatePattern == candidate {
					return true
				}
				if strings.HasSuffix(candidatePattern, "*") && strings.HasPrefix(candidate, strings.TrimSuffix(candidatePattern, "*")) {
					return true
				}
			}
		}
	}
	return false
}

// FilterModelsByHiddenList removes denied models while preserving catalog order.
func FilterModelsByHiddenList(modelIDs []string, group *Group) []string {
	if group == nil || len(group.ModelsListConfig.HiddenModels) == 0 {
		return modelIDs
	}
	filtered := make([]string, 0, len(modelIDs))
	for _, modelID := range modelIDs {
		if !group.IsModelHidden(modelID) {
			filtered = append(filtered, modelID)
		}
	}
	return filtered
}
