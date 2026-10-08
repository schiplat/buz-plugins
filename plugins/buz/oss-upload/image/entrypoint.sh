#!/bin/sh
set -eu

: "${INPUT_SOURCE:?source is required}"
: "${INPUT_BUCKET:?bucket is required}"
: "${INPUT_OBJECT:?object is required}"
: "${INPUT_ENDPOINT:?endpoint is required}"
: "${INPUT_ACCESS_KEY_ID:?access_key_id is required}"
: "${INPUT_ACCESS_KEY_SECRET:?access_key_secret is required}"
: "${INPUT_REGION:?region is required}"

case "$INPUT_SOURCE" in
  /*|..|../*|*/../*|*/..)
    printf 'source must be a relative path inside the Buz workspace\n' >&2
    exit 2
    ;;
esac

SOURCE=$(realpath -e -- "$INPUT_SOURCE")
case "$SOURCE" in
  /buz/workspace/*) ;;
  *) printf 'source must resolve to a file inside the Buz workspace\n' >&2; exit 2 ;;
esac
if [ ! -f "$SOURCE" ] || [ ! -r "$SOURCE" ]; then
  printf 'source file is not readable: %s\n' "$INPUT_SOURCE" >&2
  exit 2
fi

case "$INPUT_ENDPOINT" in
  https://?*) ;;
  *) printf 'endpoint must be an https URL\n' >&2; exit 2 ;;
esac

export OSS_ACCESS_KEY_ID="$INPUT_ACCESS_KEY_ID"
export OSS_ACCESS_KEY_SECRET="$INPUT_ACCESS_KEY_SECRET"
export OSS_ENDPOINT="$INPUT_ENDPOINT"
export OSS_REGION="$INPUT_REGION"
if [ -n "${INPUT_SESSION_TOKEN:-}" ]; then
  export OSS_SESSION_TOKEN="$INPUT_SESSION_TOKEN"
fi

exec ossutil cp "$SOURCE" "oss://$INPUT_BUCKET/$INPUT_OBJECT"
