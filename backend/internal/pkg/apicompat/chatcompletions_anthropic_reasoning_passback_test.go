package apicompat

import (
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestAnthropicToChatCompletions_ThinkingBecomesReasoningContentOnToolTurn(t *testing.T) {
	req := &AnthropicRequest{
		Model:     "deepseek-v4-flash",
		MaxTokens: 256,
		Messages: []AnthropicMessage{
			{Role: "user", Content: json.RawMessage(`"what's the weather?"`)},
			{Role: "assistant", Content: json.RawMessage(`[
				{"type":"thinking","thinking":"user wants weather, call the tool"},
				{"type":"text","text":"checking"},
				{"type":"tool_use","id":"toolu_1","name":"get_weather","input":{"city":"SF"}}
			]`)},
			{Role: "user", Content: json.RawMessage(`[{"type":"tool_result","tool_use_id":"toolu_1","content":"sunny"}]`)},
		},
	}

	out, err := AnthropicToChatCompletionsRequest(req)
	require.NoError(t, err)
	var assistant *ChatMessage
	for i := range out.Messages {
		if out.Messages[i].Role == "assistant" {
			assistant = &out.Messages[i]
			break
		}
	}
	require.NotNil(t, assistant)
	require.Len(t, assistant.ToolCalls, 1)
	require.Equal(t, "user wants weather, call the tool", assistant.ReasoningContent)
	require.Equal(t, `"checking"`, string(assistant.Content))

	payload, err := json.Marshal(out)
	require.NoError(t, err)
	require.Contains(t, string(payload), `"reasoning_content":"user wants weather, call the tool"`)
}

func TestAnthropicChatBridge_RoundTripsReasoningForToolCalls(t *testing.T) {
	upstream := ChatMessage{
		Role:             "assistant",
		ReasoningContent: "step 1: need the weather tool",
		Content:          json.RawMessage(`"checking"`),
		ToolCalls: []ChatToolCall{{
			ID:       "call_1",
			Type:     "function",
			Function: ChatFunctionCall{Name: "get_weather", Arguments: `{"city":"SF"}`},
		}},
	}

	blocks := chatMessageToAnthropicBlocks(upstream)
	require.NotEmpty(t, blocks)
	require.Equal(t, "thinking", blocks[0].Type)

	raw, err := json.Marshal(blocks)
	require.NoError(t, err)
	back, err := anthropicAssistantToChatMessages(raw)
	require.NoError(t, err)
	require.Len(t, back, 1)
	require.Equal(t, upstream.ReasoningContent, back[0].ReasoningContent)
	require.Len(t, back[0].ToolCalls, 1)
}

func TestAnthropicThinkingToReasoningContent(t *testing.T) {
	cases := []struct {
		name         string
		blocks       []AnthropicContentBlock
		hasToolCalls bool
		want         string
	}{
		{
			name:         "joins plaintext thinking blocks",
			blocks:       []AnthropicContentBlock{{Type: "thinking", Thinking: "a"}, {Type: "text", Text: "x"}, {Type: "thinking", Thinking: "b"}},
			hasToolCalls: true,
			want:         "a\nb",
		},
		{
			name:         "redacted thinking is not replayed",
			blocks:       []AnthropicContentBlock{{Type: "redacted_thinking", Signature: "opaque"}},
			hasToolCalls: true,
			want:         "",
		},
		{
			name:         "plain text turns remain unchanged",
			blocks:       []AnthropicContentBlock{{Type: "thinking", Thinking: "secret"}},
			hasToolCalls: false,
			want:         "",
		},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			require.Equal(t, tc.want, anthropicThinkingToReasoningContent(tc.blocks, tc.hasToolCalls))
		})
	}
}
