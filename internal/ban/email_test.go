package ban

import (
	"os"
	"path/filepath"
	"testing"
)

func TestNormalizeEmail(t *testing.T) {
	if got := NormalizeEmail("  Foo@Bar.COM "); got != "foo@bar.com" {
		t.Fatalf("got %q", got)
	}
}

func TestIsEmailBanned(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "banned_emails.txt")
	if err := os.WriteFile(path, []byte("# comment\nSpam@Example.com\n\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	SetEmailsFile(path)
	t.Cleanup(func() { SetEmailsFile(DefaultEmailsFile) })

	if !IsEmailBanned("spam@example.com") {
		t.Fatal("expected banned")
	}
	if IsEmailBanned("ok@example.com") {
		t.Fatal("expected not banned")
	}
	if IsEmailBanned("") {
		t.Fatal("empty must not be banned")
	}
}

func TestIsEmailBannedMissingFile(t *testing.T) {
	SetEmailsFile(filepath.Join(t.TempDir(), "nope.txt"))
	t.Cleanup(func() { SetEmailsFile(DefaultEmailsFile) })
	if IsEmailBanned("a@b.c") {
		t.Fatal("missing file must not ban")
	}
}
