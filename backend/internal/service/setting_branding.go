package service

import (
	"context"
	"errors"
	"fmt"
	"strings"
)

const legacySiteName = "Nove"

// MigrateLegacySiteName corrects the original Nova branding typo without
// overwriting a site name that an administrator has customized.
func (s *SettingService) MigrateLegacySiteName(ctx context.Context) error {
	if s == nil || s.settingRepo == nil {
		return nil
	}

	value, err := s.settingRepo.GetValue(ctx, SettingKeySiteName)
	if errors.Is(err, ErrSettingNotFound) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("read site name for branding migration: %w", err)
	}
	if strings.TrimSpace(value) != legacySiteName {
		return nil
	}

	if err := s.settingRepo.Set(ctx, SettingKeySiteName, defaultSiteName); err != nil {
		return fmt.Errorf("write migrated site name: %w", err)
	}
	return nil
}
