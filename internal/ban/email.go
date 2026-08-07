package ban

import (
	"bufio"
	"os"
	"strings"
	"sync"
)

const DefaultEmailsFile = "./data/banned_emails.txt"

var (
	mu       sync.Mutex
	filePath = DefaultEmailsFile
)

// SetEmailsFile overrides the ban list path (tests / custom deploy).
func SetEmailsFile(path string) {
	mu.Lock()
	defer mu.Unlock()
	filePath = path
}

// NormalizeEmail lowercases and trims an email for ban-list matching.
func NormalizeEmail(email string) string {
	return strings.ToLower(strings.TrimSpace(email))
}

// IsEmailBanned reports whether email is listed in the ban file.
// Missing file means nobody is banned. File is re-read each call (list stays small).
func IsEmailBanned(email string) bool {
	norm := NormalizeEmail(email)
	if norm == "" {
		return false
	}

	mu.Lock()
	path := filePath
	mu.Unlock()

	f, err := os.Open(path)
	if err != nil {
		return false
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if NormalizeEmail(line) == norm {
			return true
		}
	}
	return false
}
