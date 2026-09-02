package apicompat

import (
	"testing"

	"github.com/stretchr/testify/require"
)

func TestServiceTierPreservedAcrossBufferedBridges(t *testing.T) {
	chat := &ChatCompletionsResponse{Model: "gpt-5.5", ServiceTier: "default"}
	responses := ChatCompletionsResponseToResponses(chat, "gpt-5.5", nil, nil, false, nil)
	require.Equal(t, "default", responses.ServiceTier)

	converted := ResponsesToChatCompletions(responses, "gpt-5.5")
	require.Equal(t, "default", converted.ServiceTier)
}

func TestServiceTierPreservedAcrossStreamingBridges(t *testing.T) {
	ccState := NewChatCompletionsToResponsesStreamState("gpt-5.5")
	ccEvents := ChatCompletionsChunkToResponsesEvents(&ChatCompletionsChunk{
		Model:       "gpt-5.5",
		ServiceTier: "priority",
		Choices:     []ChatChunkChoice{{Delta: ChatDelta{Content: stringPtr("ok")}}},
	}, ccState)
	require.NotEmpty(t, ccEvents)
	require.Equal(t, "priority", ccState.ServiceTier)

	final := FinalizeChatCompletionsResponsesStream(ccState)
	var completed *ResponsesResponse
	for _, event := range final {
		if event.Type == "response.completed" {
			completed = event.Response
		}
	}
	require.NotNil(t, completed)
	require.Equal(t, "priority", completed.ServiceTier)

	chatState := NewResponsesEventToChatState()
	created := ResponsesEventToChatChunks(&ResponsesStreamEvent{
		Type: "response.created",
		Response: &ResponsesResponse{
			Model:       "gpt-5.5",
			ServiceTier: "default",
		},
	}, chatState)
	require.NotEmpty(t, created)
	require.Equal(t, "default", chatState.ServiceTier)
	require.Equal(t, "default", created[0].ServiceTier)
}
