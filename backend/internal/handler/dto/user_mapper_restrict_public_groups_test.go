package dto

import (
	"encoding/json"
	"testing"

	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/stretchr/testify/require"
)

func TestUserFromServiceAdminExposesRestrictPublicGroupsOnlyToAdmins(t *testing.T) {
	user := &service.User{
		ID:                   42,
		Email:                "restricted@example.com",
		Status:               service.StatusActive,
		RestrictPublicGroups: true,
	}

	admin := UserFromServiceAdmin(user)
	require.NotNil(t, admin)
	require.True(t, admin.RestrictPublicGroups)

	publicPayload, err := json.Marshal(UserFromService(user))
	require.NoError(t, err)
	require.NotContains(t, string(publicPayload), "restrict_public_groups")
}
