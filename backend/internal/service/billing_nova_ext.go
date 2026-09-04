package service

import "fmt"

// 本文件集中收纳 Nova 独有的长上下文计费扩展，与上游 billing_service.go 解耦：
// - 符号均为 Nova 私有语义，上游不存在同名定义，放入独立文件后上游任何演进都不会触碰这里
// - billing_service.go 中的引用（CalculateCost 内部、默认价卡映射）为同包调用，无需改动

const (
	openAIGPT54LongContextInputThreshold   = 272000
	openAIGPT54LongContextInputMultiplier  = 2.0
	openAIGPT54LongContextOutputMultiplier = 1.5
)

// usesOpenAILegacyLongContextPricing 判定该模型走 Nova 旧版"整次会话长上下文提升"名单。
// 上游以目录 above_XXXk 折算实现同一能力，Nova 保留名单兜底（gpt-5.4/5.5/5.5-pro）。
func usesOpenAILegacyLongContextPricing(normalized string) bool {
	return normalized == "gpt-5.4" || normalized == "gpt-5.5" || normalized == "gpt-5.5-pro"
}

// longContextMultiplierOrOne 把长上下文倍率归一为 1：目录数据单侧漏配（≤0）时按 1x 计费，
// 防止直乘 0 导致该分项免费（上游同款防御）。Nova"显式 0 关闭阶梯"的语义由阈值与
// LongContextExplicit 在启用判定层处理，不受此归一影响。
func longContextMultiplierOrOne(m float64) float64 {
	if m <= 0 {
		return 1
	}
	return m
}

// CalculateCostWithLongContext 计算费用，支持长上下文双倍计费
// threshold: 阈值（如 200000），超过此值的部分按 extraMultiplier 倍计费
// extraMultiplier: 超出部分的倍率（如 2.0 表示双倍）
//
// 示例：缓存 210k + 输入 10k = 220k，阈值 200k，倍率 2.0
// 拆分为：范围内 (200k, 0) + 范围外 (10k, 10k)
// 范围内正常计费，范围外 × 2 计费
func (s *BillingService) CalculateCostWithLongContext(model string, tokens UsageTokens, rateMultiplier float64, threshold int, extraMultiplier float64) (*CostBreakdown, error) {
	// 未启用长上下文计费，直接走正常计费
	if threshold <= 0 || extraMultiplier <= 1 {
		return s.CalculateCost(model, tokens, rateMultiplier)
	}

	// 计算总输入 token（缓存读取 + 新输入）
	total := tokens.CacheReadTokens + tokens.InputTokens
	if total <= threshold {
		return s.CalculateCost(model, tokens, rateMultiplier)
	}

	// 拆分成范围内和范围外
	var inRangeCacheTokens, inRangeInputTokens int
	var outRangeCacheTokens, outRangeInputTokens int

	if tokens.CacheReadTokens >= threshold {
		// 缓存已超过阈值：范围内只有缓存，范围外是超出的缓存+全部输入
		inRangeCacheTokens = threshold
		inRangeInputTokens = 0
		outRangeCacheTokens = tokens.CacheReadTokens - threshold
		outRangeInputTokens = tokens.InputTokens
	} else {
		// 缓存未超过阈值：范围内是全部缓存+部分输入，范围外是剩余输入
		inRangeCacheTokens = tokens.CacheReadTokens
		inRangeInputTokens = threshold - tokens.CacheReadTokens
		outRangeCacheTokens = 0
		outRangeInputTokens = tokens.InputTokens - inRangeInputTokens
	}

	// 范围内部分：正常计费
	inRangeTokens := UsageTokens{
		InputTokens:           inRangeInputTokens,
		OutputTokens:          tokens.OutputTokens, // 输出只算一次
		CacheCreationTokens:   tokens.CacheCreationTokens,
		CacheReadTokens:       inRangeCacheTokens,
		CacheCreation5mTokens: tokens.CacheCreation5mTokens,
		CacheCreation1hTokens: tokens.CacheCreation1hTokens,
		ImageOutputTokens:     tokens.ImageOutputTokens,
	}
	inRangeCost, err := s.CalculateCost(model, inRangeTokens, rateMultiplier)
	if err != nil {
		return nil, err
	}

	// 范围外部分：× extraMultiplier 计费
	outRangeTokens := UsageTokens{
		InputTokens:     outRangeInputTokens,
		CacheReadTokens: outRangeCacheTokens,
	}
	outRangeCost, err := s.CalculateCost(model, outRangeTokens, rateMultiplier*extraMultiplier)
	if err != nil {
		return inRangeCost, fmt.Errorf("out-range cost: %w", err)
	}

	// 合并成本
	return &CostBreakdown{
		InputCost:                 inRangeCost.InputCost + outRangeCost.InputCost,
		ImageInputCost:            inRangeCost.ImageInputCost + outRangeCost.ImageInputCost,
		OutputCost:                inRangeCost.OutputCost,
		ImageOutputCost:           inRangeCost.ImageOutputCost,
		CacheCreationCost:         inRangeCost.CacheCreationCost,
		CacheReadCost:             inRangeCost.CacheReadCost + outRangeCost.CacheReadCost,
		TotalCost:                 inRangeCost.TotalCost + outRangeCost.TotalCost,
		ActualCost:                inRangeCost.ActualCost + outRangeCost.ActualCost,
		LongContextBillingApplied: outRangeCost.ActualCost > 0,
	}, nil
}
