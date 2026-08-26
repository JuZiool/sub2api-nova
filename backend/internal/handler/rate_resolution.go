package handler

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/gin-gonic/gin"
)

func resolveRequestRateResolution(ctx context.Context, apiKey *service.APIKey, requestedModel string, pricingAt time.Time, gateway *service.GatewayService, openAI *service.OpenAIGatewayService) (*service.RateResolution, error) {
	if apiKey == nil || apiKey.Group == nil || strings.TrimSpace(requestedModel) == "" {
		return nil, nil
	}
	if pricingAt.IsZero() {
		pricingAt = time.Now().UTC()
	}
	if apiKey.Group.Platform == service.PlatformOpenAI || apiKey.Group.Platform == service.PlatformGrok {
		if openAI == nil {
			return nil, fmt.Errorf("openai gateway service is unavailable")
		}
		return openAI.ResolveRequestRateResolution(ctx, apiKey.UserID, apiKey.Group, requestedModel, pricingAt)
	}
	if gateway == nil {
		return nil, fmt.Errorf("gateway service is unavailable")
	}
	return gateway.ResolveRequestRateResolution(ctx, apiKey.UserID, apiKey.Group, requestedModel, pricingAt)
}

// freezeRequestRateResolution resolves the user-side model multiplier after
// the client model is known but before account selection/model mapping. The
// frozen object is carried in the request context so detached usage workers
// cannot re-read changed group rules during settlement.
func freezeRequestRateResolution(c *gin.Context, apiKey *service.APIKey, requestedModel string, pricingAt time.Time, gateway *service.GatewayService, openAI *service.OpenAIGatewayService) error {
	if c == nil {
		return nil
	}
	resolution, err := resolveRequestRateResolution(c.Request.Context(), apiKey, requestedModel, pricingAt, gateway, openAI)
	if err != nil {
		return err
	}
	c.Request = c.Request.WithContext(service.WithRateResolution(c.Request.Context(), resolution))
	return nil
}

// freezeFallbackGroupRateResolution is used only when an upstream retry truly
// switches the pricing owner to a configured fallback group before any usable
// upstream output was returned. Ordinary account failover must keep the first
// request snapshot unchanged.
func freezeFallbackGroupRateResolution(c *gin.Context, apiKey *service.APIKey, requestedModel string, pricingAt time.Time, gateway *service.GatewayService, openAI *service.OpenAIGatewayService) error {
	if c == nil {
		return nil
	}
	resolution, err := resolveRequestRateResolution(c.Request.Context(), apiKey, requestedModel, pricingAt, gateway, openAI)
	if err != nil {
		return err
	}
	if resolution != nil {
		resolution.PricingOwnerSource = "fallback_group"
	}
	c.Request = c.Request.WithContext(service.WithRateResolution(c.Request.Context(), resolution))
	return nil
}
