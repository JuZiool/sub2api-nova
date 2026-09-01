package service

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestWriteOpenAICompactSSEFailureMessage_CarriesCreatedAt(t *testing.T) {
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	context, _ := gin.CreateTestContext(recorder)
	context.Request = httptest.NewRequest(http.MethodPost, "/v1/responses", nil)

	writeOpenAICompactSSEFailureMessage(context, http.StatusBadGateway, "upstream_error", "boom")

	_, payload, found := strings.Cut(recorder.Body.String(), "data: ")
	require.True(t, found)

	var event struct {
		Type     string `json:"type"`
		Response struct {
			CreatedAt int64  `json:"created_at"`
			Status    string `json:"status"`
		} `json:"response"`
	}
	require.NoError(t, json.Unmarshal([]byte(strings.TrimSpace(payload)), &event))
	require.Equal(t, "response.failed", event.Type)
	require.Equal(t, "failed", event.Response.Status)
	require.Greater(t, event.Response.CreatedAt, int64(0))
}
