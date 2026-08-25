package service

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestValidateOpenAIServiceTierField(t *testing.T) {
	tests := []struct {
		name string
		body string
		want string
	}{
		{name: "missing", body: `{"model":"gpt-5"}`},
		{name: "null", body: `{"service_tier":null}`},
		{name: "fast alias", body: `{"service_tier":"fast"}`, want: "priority"},
		{name: "priority", body: `{"service_tier":"priority"}`, want: "priority"},
		{name: "official values", body: `{"service_tier":"scale"}`, want: "scale"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ValidateOpenAIServiceTierField([]byte(tt.body))
			require.NoError(t, err)
			require.Equal(t, tt.want, got)
		})
	}
}

func TestValidateOpenAIServiceTierFieldRejectsInvalidValues(t *testing.T) {
	for _, body := range []string{
		`{"service_tier":""}`,
		`{"service_tier":"turbo"}`,
		`{"service_tier":true}`,
		`{"service_tier":123}`,
	} {
		_, err := ValidateOpenAIServiceTierField([]byte(body))
		require.Error(t, err, body)
		require.ErrorAs(t, err, new(*ErrInvalidOpenAIServiceTier))
	}
}
