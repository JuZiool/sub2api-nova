//go:build unit

package service

import (
	"context"
	"errors"
	"testing"

	"github.com/stretchr/testify/require"
)

type brandingSettingRepoStub struct {
	value    string
	getErr   error
	setErr   error
	setKey   string
	setValue string
}

func (s *brandingSettingRepoStub) Get(context.Context, string) (*Setting, error) {
	panic("unexpected Get call")
}

func (s *brandingSettingRepoStub) GetValue(context.Context, string) (string, error) {
	if s.getErr != nil {
		return "", s.getErr
	}
	return s.value, nil
}

func (s *brandingSettingRepoStub) Set(_ context.Context, key, value string) error {
	s.setKey = key
	s.setValue = value
	return s.setErr
}

func (s *brandingSettingRepoStub) GetMultiple(context.Context, []string) (map[string]string, error) {
	panic("unexpected GetMultiple call")
}

func (s *brandingSettingRepoStub) SetMultiple(context.Context, map[string]string) error {
	panic("unexpected SetMultiple call")
}

func (s *brandingSettingRepoStub) GetAll(context.Context) (map[string]string, error) {
	panic("unexpected GetAll call")
}

func (s *brandingSettingRepoStub) Delete(context.Context, string) error {
	panic("unexpected Delete call")
}

func TestSettingService_MigrateLegacySiteName(t *testing.T) {
	t.Run("replaces legacy typo", func(t *testing.T) {
		repo := &brandingSettingRepoStub{value: legacySiteName}
		svc := NewSettingService(repo, nil)

		require.NoError(t, svc.MigrateLegacySiteName(context.Background()))
		require.Equal(t, SettingKeySiteName, repo.setKey)
		require.Equal(t, defaultSiteName, repo.setValue)
	})

	t.Run("preserves custom site name", func(t *testing.T) {
		repo := &brandingSettingRepoStub{value: "My Site"}
		svc := NewSettingService(repo, nil)

		require.NoError(t, svc.MigrateLegacySiteName(context.Background()))
		require.Empty(t, repo.setKey)
	})

	t.Run("ignores missing setting", func(t *testing.T) {
		repo := &brandingSettingRepoStub{getErr: ErrSettingNotFound}
		svc := NewSettingService(repo, nil)

		require.NoError(t, svc.MigrateLegacySiteName(context.Background()))
	})

	t.Run("returns read and write errors", func(t *testing.T) {
		readErr := errors.New("database unavailable")
		repo := &brandingSettingRepoStub{getErr: readErr}
		svc := NewSettingService(repo, nil)
		require.ErrorIs(t, svc.MigrateLegacySiteName(context.Background()), readErr)

		repo = &brandingSettingRepoStub{value: legacySiteName, setErr: errors.New("write failed")}
		svc = NewSettingService(repo, nil)
		require.ErrorContains(t, svc.MigrateLegacySiteName(context.Background()), "write failed")
	})
}
