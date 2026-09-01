package routes

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	middleware2 "github.com/Wei-Shaw/sub2api/internal/server/middleware"
	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestHiddenModelMiddlewareRejectsOriginalCompositeModel(t *testing.T) {
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(recorder)
	c.Request = httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(`{"model":"public-gpt","messages":[]}`))
	c.Request.Header.Set("Content-Type", "application/json")
	c.Set(string(middleware2.ContextKeyAPIKey), &service.APIKey{
		Group: &service.Group{ModelsListConfig: service.GroupModelsListConfig{HiddenModels: []string{"public-gpt"}}},
	})

	hiddenModelMiddleware()(c)

	require.Equal(t, http.StatusForbidden, recorder.Code)
	require.Contains(t, recorder.Body.String(), "not available")
}

func TestHiddenModelMiddlewareMatchesGeminiPathModel(t *testing.T) {
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(recorder)
	c.Request = httptest.NewRequest(http.MethodGet, "/v1beta/models/gemini-3-pro", nil)
	c.Params = gin.Params{{Key: "model", Value: "gemini-3-pro"}}
	c.Set(string(middleware2.ContextKeyAPIKey), &service.APIKey{
		Group: &service.Group{ModelsListConfig: service.GroupModelsListConfig{HiddenModels: []string{"gemini-3-*"}}},
	})

	hiddenModelMiddleware()(c)

	require.Equal(t, http.StatusForbidden, recorder.Code)
}
