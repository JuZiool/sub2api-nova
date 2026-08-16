//go:build unit

package admin

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestSystemHandlerGetVersionReturnsLocalBuildVersion(t *testing.T) {
	gin.SetMode(gin.TestMode)
	handler := NewSystemHandler("0.1.177-overdraft.6", nil)
	router := gin.New()
	router.GET("/api/v1/admin/system/version", handler.GetVersion)

	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/v1/admin/system/version", nil)
	router.ServeHTTP(recorder, request)

	require.Equal(t, http.StatusOK, recorder.Code)
	var envelope struct {
		Data struct {
			Version string `json:"version"`
		} `json:"data"`
	}
	require.NoError(t, json.Unmarshal(recorder.Body.Bytes(), &envelope))
	require.Equal(t, "0.1.177-overdraft.6", envelope.Data.Version)
}
