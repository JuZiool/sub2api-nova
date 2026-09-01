package service

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestGroupModelHiddenRulesNormalizeAndMatch(t *testing.T) {
	group := &Group{ModelsListConfig: GroupModelsListConfig{
		HiddenModels: []string{" gpt-5.4 ", "gpt-5.4", "gemini-3-*", "models/blocked-model"},
	}}

	require.True(t, group.IsModelHidden("gpt-5.4"))
	require.True(t, group.IsModelHidden("gemini-3-pro"))
	require.True(t, group.IsModelHidden("models/blocked-model"))
	require.True(t, group.IsModelHidden("blocked-model"))
	require.False(t, group.IsModelHidden("gpt-5.5"))

	normalized := normalizeGroupModelsListConfig(group.ModelsListConfig)
	require.Equal(t, []string{"gpt-5.4", "gemini-3-*", "models/blocked-model"}, normalized.HiddenModels)
}

func TestFilterModelsByHiddenListPreservesOrder(t *testing.T) {
	group := &Group{ModelsListConfig: GroupModelsListConfig{
		HiddenModels: []string{"gpt-5.4", "gemini-*"},
	}}

	require.Equal(t,
		[]string{"gpt-5.5", "custom-model"},
		FilterModelsByHiddenList([]string{"gpt-5.4", "gpt-5.5", "gemini-3-pro", "custom-model"}, group),
	)
}
