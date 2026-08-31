package service

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/config"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func newPassthroughKeepaliveTestContext(t *testing.T) (*gin.Context, *httptest.ResponseRecorder) {
	t.Helper()
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(recorder)
	c.Request = httptest.NewRequest(http.MethodPost, "/v1/responses", nil)
	return c, recorder
}

func TestStartOpenAISSEKeepalive_WorksWithoutCompactMarker(t *testing.T) {
	c, recorder := newPassthroughKeepaliveTestContext(t)

	stop := StartOpenAICompactSSEKeepalive(c, keepaliveTestInterval)
	waitForKeepaliveBeats()
	stop()
	require.Zero(t, recorder.Body.Len())

	c, recorder = newPassthroughKeepaliveTestContext(t)
	stop = startOpenAISSEKeepalive(c, keepaliveTestInterval)
	defer stop()
	waitForKeepaliveBeats()

	require.True(t, StopOpenAICompactSSEKeepaliveCommitted(c))
	require.Equal(t, http.StatusOK, recorder.Code)
	require.Equal(t, "text/event-stream", recorder.Header().Get("Content-Type"))
	require.Equal(t, "no", recorder.Header().Get("X-Accel-Buffering"))
	require.Contains(t, recorder.Body.String(), ": keepalive\n\n")
}

func TestPassthroughKeepaliveDoesNotBlockPreOutputFailover(t *testing.T) {
	c, recorder := newPassthroughKeepaliveTestContext(t)
	stop := startOpenAISSEKeepalive(c, keepaliveTestInterval)
	defer stop()
	waitForKeepaliveBeats()

	require.True(t, StopOpenAICompactSSEKeepaliveCommitted(c))
	require.NotZero(t, recorder.Body.Len())
	require.False(t, openAIStreamClientOutputStarted(c, false))

	_, err := c.Writer.Write([]byte("data: {\"type\":\"response.output_text.delta\"}\n\n"))
	require.NoError(t, err)
	require.True(t, openAIStreamClientOutputStarted(c, false))
}

func TestPassthroughKeepaliveStopsBeforeHandingOverWriter(t *testing.T) {
	c, recorder := newPassthroughKeepaliveTestContext(t)
	stop := startOpenAISSEKeepalive(c, keepaliveTestInterval)
	waitForKeepaliveBeats()
	stop()

	before := recorder.Body.String()
	waitForKeepaliveBeats()
	require.Equal(t, before, recorder.Body.String())

	_, err := c.Writer.Write([]byte("data: real\n\n"))
	require.NoError(t, err)
	waitForKeepaliveBeats()
	require.True(t, strings.HasSuffix(recorder.Body.String(), "data: real\n\n"))
}

func TestPassthroughKeepaliveDisabledKeepsWriterUntouched(t *testing.T) {
	c, recorder := newPassthroughKeepaliveTestContext(t)
	stop := startOpenAISSEKeepalive(c, 0)
	waitForKeepaliveBeats()
	stop()

	require.Zero(t, recorder.Body.Len())
	require.False(t, StopOpenAICompactSSEKeepaliveCommitted(c))
}

func TestStreamingResponsePassthroughEmitsPreOutputKeepalive(t *testing.T) {
	c, recorder := newPassthroughKeepaliveTestContext(t)
	reader, writer := io.Pipe()
	defer reader.Close()
	defer writer.Close()
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"text/event-stream"}},
		Body:       reader,
	}
	svc := &OpenAIGatewayService{cfg: &config.Config{
		Gateway: config.GatewayConfig{StreamKeepaliveInterval: 1},
	}}
	result := make(chan error, 1)
	go func() {
		_, err := svc.handleStreamingResponsePassthrough(
			context.Background(), resp, c, &Account{ID: 1}, time.Now(), "gpt-5", "gpt-5",
		)
		result <- err
	}()

	time.Sleep(1200 * time.Millisecond)
	require.True(t, StopOpenAICompactSSEKeepaliveCommitted(c))
	require.Contains(t, recorder.Body.String(), ": keepalive\n\n")
	require.False(t, openAIStreamClientOutputStarted(c, false))

	_, err := io.WriteString(writer, "data: {\"type\":\"response.output_text.delta\",\"delta\":\"ok\"}\n\ndata: [DONE]\n\n")
	require.NoError(t, err)
	require.NoError(t, writer.Close())

	select {
	case err := <-result:
		require.NoError(t, err)
	case <-time.After(3 * time.Second):
		t.Fatal("streaming passthrough did not complete")
	}
	require.Contains(t, recorder.Body.String(), "response.output_text.delta")
}

func TestStreamingResponsePassthroughSkipsNativeCompactionV2(t *testing.T) {
	c, _ := newPassthroughKeepaliveTestContext(t)
	MarkOpenAINativeCompactionV2(c)
	resp := &http.Response{
		StatusCode: http.StatusOK,
		Header:     http.Header{"Content-Type": []string{"text/event-stream"}},
		Body: io.NopCloser(strings.NewReader(
			"data: {\"type\":\"response.output_text.delta\",\"delta\":\"ok\"}\n\ndata: [DONE]\n\n",
		)),
	}
	svc := &OpenAIGatewayService{cfg: &config.Config{
		Gateway: config.GatewayConfig{StreamKeepaliveInterval: 1},
	}}

	result, err := svc.handleStreamingResponsePassthrough(
		context.Background(), resp, c, &Account{ID: 1}, time.Now(), "gpt-5", "gpt-5",
	)

	require.NoError(t, err)
	require.NotNil(t, result)
	_, started := c.Get(openAICompactSSEKeepaliveKey)
	require.False(t, started)
}
