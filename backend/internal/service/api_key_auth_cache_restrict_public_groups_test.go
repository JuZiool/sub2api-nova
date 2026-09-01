package service

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/require"
)

func restrictedPublicGroupsAPIKey() *APIKey {
	groupID := int64(50)
	return &APIKey{
		ID:      83,
		UserID:  41,
		GroupID: &groupID,
		Key:     "sk-restrict-public-groups",
		Name:    "restrict-public-groups",
		Status:  StatusActive,
		User: &User{
			ID:                   41,
			Status:               StatusActive,
			RestrictPublicGroups: true,
			AllowedGroups:        []int64{groupID},
		},
	}
}

func TestAPIKeyAuthSnapshotRestrictPublicGroupsRoundTrip(t *testing.T) {
	svc := &APIKeyService{}
	apiKey := restrictedPublicGroupsAPIKey()

	snapshot := svc.snapshotFromAPIKey(context.Background(), apiKey)
	require.NotNil(t, snapshot)
	require.True(t, snapshot.User.RestrictPublicGroups)

	payload, err := json.Marshal(&APIKeyAuthCacheEntry{Snapshot: snapshot})
	require.NoError(t, err)

	var restored APIKeyAuthCacheEntry
	require.NoError(t, json.Unmarshal(payload, &restored))

	materialized, used, err := svc.applyAuthCacheEntry(apiKey.Key, &restored)
	require.NoError(t, err)
	require.True(t, used)
	require.NotNil(t, materialized.User)
	require.True(t, materialized.User.RestrictPublicGroups)
	require.True(t, materialized.User.CanBindGroup(*apiKey.GroupID, false))
	require.False(t, materialized.User.CanBindGroup(*apiKey.GroupID+1, false))
}

func TestAPIKeyAuthSnapshotV21EvictedAfterPublicGroupRestriction(t *testing.T) {
	svc := &APIKeyService{}
	snapshot := svc.snapshotFromAPIKey(context.Background(), restrictedPublicGroupsAPIKey())
	require.NotNil(t, snapshot)
	snapshot.Version = 21

	materialized, used, err := svc.applyAuthCacheEntry("sk-v21", &APIKeyAuthCacheEntry{Snapshot: snapshot})
	require.NoError(t, err)
	require.False(t, used, "v21 does not carry the public-group authorization contract")
	require.Nil(t, materialized)
}
