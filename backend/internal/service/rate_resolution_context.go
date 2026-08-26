package service

import "context"

// requestRateResolutionContextKey carries the immutable user-side pricing
// decision from the request-start handler into detached usage workers.
// It intentionally stores a pointer to a fully populated RateResolution;
// callers must not mutate it after attaching it to a request.
type requestRateResolutionContextKey struct{}

func WithRateResolution(ctx context.Context, resolution *RateResolution) context.Context {
	if ctx == nil {
		ctx = context.Background()
	}
	if resolution == nil {
		return ctx
	}
	return context.WithValue(ctx, requestRateResolutionContextKey{}, resolution)
}

func RateResolutionFromContext(ctx context.Context) *RateResolution {
	if ctx == nil {
		return nil
	}
	resolution, _ := ctx.Value(requestRateResolutionContextKey{}).(*RateResolution)
	return resolution
}
