package entity

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCheckPassword(t *testing.T) {
	empty := User{}
	assert.False(t, empty.CheckPassword("any"))

	plain := User{Password: "secret"}
	plain.ID = 1
	assert.True(t, plain.CheckPassword("secret"))
	assert.False(t, plain.CheckPassword("wrong"))
	assert.False(t, plain.CheckPassword(""))

	hashed := User{}
	hashed.ID = 1
	require.NoError(t, hashed.SetPasswordEncrypt("secret"))
	assert.True(t, hashed.CheckPassword("secret"))
	assert.False(t, hashed.CheckPassword("wrong"))

	legacyMD5 := User{Password: "(md5)5ebe2294ecd0e0f08eab7690d2a6ee69"}
	legacyMD5.ID = 1
	assert.False(t, legacyMD5.CheckPassword("secret"))
}
