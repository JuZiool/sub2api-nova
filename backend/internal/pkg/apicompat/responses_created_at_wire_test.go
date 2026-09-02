package apicompat

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/require"
)

func responseObjectOf(t *testing.T, evt ResponsesStreamEvent) map[string]any {
	t.Helper()
	payload := marshalEvent(t, evt)
	response, ok := payload["response"].(map[string]any)
	require.True(t, ok, "event must carry a response object: %v", payload)
	return response
}

func requireResponseCreatedAt(t *testing.T, response map[string]any) int64 {
	t.Helper()
	raw, ok := response["created_at"]
	require.True(t, ok, "response object must include created_at")
	value, ok := raw.(float64)
	require.True(t, ok, "created_at must be numeric, got %T", raw)
	require.Greater(t, int64(value), int64(0))
	return int64(value)
}

func TestResponsesWire_CreatedAtPresentEvenAtZero(t *testing.T) {
	response := responseObjectOf(t, ResponsesStreamEvent{
		Type:     "response.created",
		Response: &ResponsesResponse{ID: "resp_1", Object: "response", Status: "in_progress"},
	})
	require.Contains(t, response, "created_at", "created_at must not use omitempty")
	require.EqualValues(t, 0, response["created_at"])
}

func TestChatCompletionsResponseToResponses_CarriesCreatedAt(t *testing.T) {
	withUpstreamTime := ChatCompletionsResponseToResponses(&ChatCompletionsResponse{
		ID:      "chatcmpl_1",
		Created: 1700000000,
		Model:   "deepseek-v4-flash",
		Choices: []ChatChoice{{Message: ChatMessage{Role: "assistant", Content: json.RawMessage(`"hi"`)}}},
	}, "deepseek-v4-flash", nil, nil, false, nil)
	require.EqualValues(t, 1700000000, withUpstreamTime.CreatedAt)

	withoutUpstreamTime := ChatCompletionsResponseToResponses(nil, "deepseek-v4-flash", nil, nil, false, nil)
	require.Greater(t, withoutUpstreamTime.CreatedAt, int64(0))
}

func TestChatCompletionsToResponsesStream_CreatedAtStableAcrossEvents(t *testing.T) {
	state := NewChatCompletionsToResponsesStreamState("deepseek-v4-flash")
	var chunk ChatCompletionsChunk
	require.NoError(t, json.Unmarshal([]byte(`{"choices":[{"index":0,"delta":{"content":"hi"}}]}`), &chunk))

	events := ChatCompletionsChunkToResponsesEvents(&chunk, state)
	events = append(events, FinalizeChatCompletionsResponsesStream(state)...)

	seen := map[string]int64{}
	for _, event := range events {
		if event.Response != nil {
			seen[event.Type] = requireResponseCreatedAt(t, responseObjectOf(t, event))
		}
	}
	require.Equal(t, state.Created, seen["response.created"])
	require.Equal(t, seen["response.created"], seen["response.completed"])
}

func TestAnthropicToResponses_CarriesCreatedAt(t *testing.T) {
	nonStreaming := AnthropicToResponsesResponse(&AnthropicResponse{
		ID:      "msg_1",
		Type:    "message",
		Role:    "assistant",
		Model:   "claude-sonnet-4-20250514",
		Content: []AnthropicContentBlock{{Type: "text", Text: "hi"}},
	})
	require.Greater(t, nonStreaming.CreatedAt, int64(0))

	state := NewAnthropicEventToResponsesState()
	state.Model = "claude-sonnet-4-20250514"
	var events []ResponsesStreamEvent
	for _, raw := range []string{
		`{"type":"message_start","message":{"id":"msg_1","type":"message","role":"assistant","model":"claude-sonnet-4-20250514","content":[]}}`,
		`{"type":"message_stop"}`,
	} {
		var event AnthropicStreamEvent
		require.NoError(t, json.Unmarshal([]byte(raw), &event))
		events = append(events, AnthropicEventToResponsesEvents(&event, state)...)
	}

	seen := map[string]int64{}
	for _, event := range events {
		if event.Response != nil {
			seen[event.Type] = requireResponseCreatedAt(t, responseObjectOf(t, event))
		}
	}
	require.Equal(t, state.Created, seen["response.created"])
	require.Equal(t, seen["response.created"], seen["response.completed"])
}

func TestResponsesStreamEvent_CreatedAtSurvivesUnmarshalRemarshal(t *testing.T) {
	upstream := []byte(`{"type":"response.completed","response":{"id":"resp_9","object":"response","created_at":1700000123,"model":"gpt-5.5","status":"completed","output":[]}}`)
	var event ResponsesStreamEvent
	require.NoError(t, json.Unmarshal(upstream, &event))
	require.EqualValues(t, 1700000123, event.Response.CreatedAt)
	require.EqualValues(t, 1700000123, requireResponseCreatedAt(t, responseObjectOf(t, event)))
}
