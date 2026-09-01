package service

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func newRawStreamTruncationTestContext(t *testing.T) (*gin.Context, *httptest.ResponseRecorder) {
	t.Helper()
	gin.SetMode(gin.TestMode)
	recorder := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(recorder)
	c.Request = httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil)
	return c, recorder
}

func newRawStreamTruncationResponse(body string) *http.Response {
	return &http.Response{
		StatusCode: http.StatusOK,
		Header: http.Header{
			"Content-Type": []string{"text/event-stream"},
			"X-Request-Id": []string{"rid-raw-truncated"},
		},
		Body: io.NopCloser(strings.NewReader(body)),
	}
}

func rawStreamTruncationAccount() *Account {
	return &Account{ID: 991, Name: "raw-stream-test", Platform: PlatformOpenAI}
}

type rawStreamTruncationErrorBody struct {
	payload []byte
	err     error
	read    bool
}

func (b *rawStreamTruncationErrorBody) Read(p []byte) (int, error) {
	if b.read {
		return 0, b.err
	}
	b.read = true
	return copy(p, b.payload), nil
}

func (b *rawStreamTruncationErrorBody) Close() error { return nil }

func runRawStreamTruncationTest(
	t *testing.T,
	c *gin.Context,
	resp *http.Response,
) (*OpenAIForwardResult, error) {
	t.Helper()
	return (&OpenAIGatewayService{}).streamRawChatCompletions(
		c,
		resp,
		rawStreamTruncationAccount(),
		"test-model",
		"test-model",
		"test-model",
		nil,
		nil,
		time.Now(),
		0,
	)
}

func TestRawChatStreamTruncationBeforeOutputTriggersFailover(t *testing.T) {
	c, recorder := newRawStreamTruncationTestContext(t)

	result, err := runRawStreamTruncationTest(t, c, newRawStreamTruncationResponse(""))

	require.Nil(t, result)
	var failoverErr *UpstreamFailoverError
	require.ErrorAs(t, err, &failoverErr)
	require.Equal(t, http.StatusBadGateway, failoverErr.StatusCode)
	require.Contains(t, string(failoverErr.ResponseBody), OpenAIUpstreamStreamTruncatedCode)
	require.True(t, failoverErr.ShouldRetryNextAccount())
	require.False(t, c.Writer.Written())
	require.Empty(t, recorder.Body.String())
}

func TestRawChatStreamTruncationAfterOutputReturnsTypedError(t *testing.T) {
	c, recorder := newRawStreamTruncationTestContext(t)
	upstream := "data: {\"id\":\"chatcmpl_cut\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\"partial\"},\"finish_reason\":null}]}\n\n"

	result, err := runRawStreamTruncationTest(t, c, newRawStreamTruncationResponse(upstream))

	require.Error(t, err)
	require.NotNil(t, result)
	var failoverErr *UpstreamFailoverError
	require.False(t, errors.As(err, &failoverErr))
	code, message, ok := OpenAIUpstreamStreamReadErrorDetails(err)
	require.True(t, ok)
	require.Equal(t, OpenAIUpstreamStreamTruncatedCode, code)
	require.Equal(t, "Upstream response stream ended before completion", message)
	require.Contains(t, recorder.Body.String(), `"content":"partial"`)

	events, ok := c.Get(OpsUpstreamErrorsKey)
	require.True(t, ok)
	require.Len(t, events.([]*OpsUpstreamErrorEvent), 1)
}

func TestRawChatStreamReadErrorAfterOutputKeepsTransportClassification(t *testing.T) {
	c, recorder := newRawStreamTruncationTestContext(t)
	upstream := "data: {\"id\":\"chatcmpl_reset\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\"partial\"},\"finish_reason\":null}]}\n\n"
	resp := newRawStreamTruncationResponse("")
	resp.Body = &rawStreamTruncationErrorBody{
		payload: []byte(upstream),
		err:     errors.New("read tcp: connection reset by peer"),
	}

	result, err := runRawStreamTruncationTest(t, c, resp)

	require.Error(t, err)
	require.NotNil(t, result)
	code, _, ok := OpenAIUpstreamStreamReadErrorDetails(err)
	require.True(t, ok)
	require.Equal(t, OpenAIUpstreamStreamReadErrorCode, code)
	require.Contains(t, recorder.Body.String(), `"content":"partial"`)
}

func TestRawChatStreamWithoutDoneUsesUsageAsTerminal(t *testing.T) {
	c, _ := newRawStreamTruncationTestContext(t)
	upstream := strings.Join([]string{
		`data: {"choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":null}]}`,
		"",
		`data: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":3,"total_tokens":10}}`,
		"",
	}, "\n")

	result, err := runRawStreamTruncationTest(t, c, newRawStreamTruncationResponse(upstream))

	require.NoError(t, err)
	require.NotNil(t, result)
	require.Equal(t, 7, result.Usage.InputTokens)
	require.Equal(t, 3, result.Usage.OutputTokens)
}

func TestRawChatStreamTruncationDoesNotAttributeCanceledRequest(t *testing.T) {
	c, _ := newRawStreamTruncationTestContext(t)
	requestContext, cancel := context.WithCancel(c.Request.Context())
	cancel()
	c.Request = c.Request.WithContext(requestContext)
	upstream := "data: {\"choices\":[{\"index\":0,\"delta\":{\"content\":\"partial\"},\"finish_reason\":null}]}\n\n"

	result, err := runRawStreamTruncationTest(t, c, newRawStreamTruncationResponse(upstream))

	require.NoError(t, err)
	require.NotNil(t, result)
	_, recorded := c.Get(OpsUpstreamErrorsKey)
	require.False(t, recorded)
}
