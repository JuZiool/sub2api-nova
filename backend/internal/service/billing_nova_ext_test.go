package service

import (
	"testing"

	"github.com/stretchr/testify/require"
)

// 回归：长上下文倍率单侧漏配 0 时按 1x 计费，不得让该分项免费（原直乘 0 漏洞）。
func TestLongContextZeroMultiplierDoesNotFreeTokens(t *testing.T) {
	pricing := &ModelPricing{
		InputPricePerToken:          1e-6,
		OutputPricePerToken:         2e-6,
		CacheReadPricePerToken:      0.2e-6,
		CacheCreationPricePerToken:  0.5e-6,
		LongContextInputThreshold:   1000,
		LongContextInputMultiplier:  0, // 目录单侧漏配：应归一为 1x
		LongContextOutputMultiplier: 2,
	}
	svc := &BillingService{}
	tokens := UsageTokens{InputTokens: 2000, OutputTokens: 100, CacheReadTokens: 500}

	bd := svc.computeTokenBreakdown(pricing, tokens, 1, "", true)

	require.InDelta(t, 2000*1e-6, bd.InputCost, 1e-12)
	require.InDelta(t, 500*0.2e-6, bd.CacheReadCost, 1e-12)
	require.InDelta(t, 100*2e-6*2, bd.OutputCost, 1e-12)
	require.Greater(t, bd.ActualCost, 0.0)
}

// 语义保留：阈值 ≤0（显式关闭阶梯）时不应用长上下文倍率，输出按普通价计费。
func TestLongContextExplicitZeroThresholdKeepsDisabledSemantics(t *testing.T) {
	pricing := &ModelPricing{
		InputPricePerToken:          1e-6,
		OutputPricePerToken:         2e-6,
		LongContextInputThreshold:   0,
		LongContextInputMultiplier:  0,
		LongContextOutputMultiplier: 0,
	}
	svc := &BillingService{}
	tokens := UsageTokens{InputTokens: 2000, OutputTokens: 100}

	bd := svc.computeTokenBreakdown(pricing, tokens, 1, "", true)

	require.InDelta(t, 2000*1e-6, bd.InputCost, 1e-12)
	require.InDelta(t, 100*2e-6, bd.OutputCost, 1e-12)
	require.False(t, bd.LongContextBillingApplied)
}
