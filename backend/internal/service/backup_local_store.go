package service

import (
	"context"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const defaultLocalBackupDir = "/app/data/backups"

// localBackupStore keeps backup archives in the persistent /app/data mount.
// Keys are always resolved below root so backup metadata cannot address other files.
type localBackupStore struct {
	root string
}

func newLocalBackupStore(root string) (*localBackupStore, error) {
	if err := os.MkdirAll(root, 0o750); err != nil {
		return nil, fmt.Errorf("create local backup directory: %w", err)
	}
	return &localBackupStore{root: root}, nil
}

func (s *localBackupStore) Upload(ctx context.Context, key string, body io.Reader, _ string) (int64, error) {
	target, err := s.resolve(key)
	if err != nil {
		return 0, err
	}
	if err := os.MkdirAll(filepath.Dir(target), 0o750); err != nil {
		return 0, fmt.Errorf("create local backup parent directory: %w", err)
	}
	temp, err := os.CreateTemp(filepath.Dir(target), ".backup-upload-*")
	if err != nil {
		return 0, fmt.Errorf("create local backup temp file: %w", err)
	}
	tempPath := temp.Name()
	defer func() { _ = os.Remove(tempPath) }()

	size, copyErr := io.Copy(temp, &contextReader{ctx: ctx, reader: body})
	closeErr := temp.Close()
	if copyErr != nil {
		return 0, fmt.Errorf("write local backup: %w", copyErr)
	}
	if closeErr != nil {
		return 0, fmt.Errorf("close local backup: %w", closeErr)
	}
	if err := os.Rename(tempPath, target); err != nil {
		return 0, fmt.Errorf("persist local backup: %w", err)
	}
	return size, nil
}

func (s *localBackupStore) UploadFile(ctx context.Context, key string, filePath string, contentType string) (int64, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return 0, fmt.Errorf("open backup archive: %w", err)
	}
	defer func() { _ = file.Close() }()
	return s.Upload(ctx, key, file, contentType)
}

func (s *localBackupStore) Download(_ context.Context, key string) (io.ReadCloser, error) {
	target, err := s.resolve(key)
	if err != nil {
		return nil, err
	}
	file, err := os.Open(target)
	if err != nil {
		return nil, fmt.Errorf("open local backup: %w", err)
	}
	return file, nil
}

func (s *localBackupStore) Delete(_ context.Context, key string) error {
	target, err := s.resolve(key)
	if err != nil {
		return err
	}
	if err := os.Remove(target); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("delete local backup: %w", err)
	}
	return nil
}

func (s *localBackupStore) PresignURL(_ context.Context, _ string, _ time.Duration) (string, error) {
	return "", fmt.Errorf("local backup storage does not support presigned URLs")
}

func (s *localBackupStore) HeadBucket(_ context.Context) error {
	return nil
}

func (s *localBackupStore) resolve(key string) (string, error) {
	cleanKey := filepath.Clean(filepath.FromSlash(strings.TrimSpace(key)))
	if cleanKey == "." || filepath.IsAbs(cleanKey) || cleanKey == ".." || strings.HasPrefix(cleanKey, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("invalid local backup key")
	}
	target := filepath.Join(s.root, cleanKey)
	rel, err := filepath.Rel(s.root, target)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("invalid local backup key")
	}
	return target, nil
}

type contextReader struct {
	ctx    context.Context
	reader io.Reader
}

func (r *contextReader) Read(p []byte) (int, error) {
	select {
	case <-r.ctx.Done():
		return 0, r.ctx.Err()
	default:
		return r.reader.Read(p)
	}
}
