#!/bin/sh
set -eu

: "${INPUT_SOURCE:?source is required}"
: "${INPUT_BUCKET:?bucket is required}"
: "${INPUT_KEY:?key is required}"
: "${INPUT_REGION:?region is required}"
: "${INPUT_ACCESS_KEY_ID:?access_key_id is required}"
: "${INPUT_SECRET_ACCESS_KEY:?secret_access_key is required}"
: "${INPUT_ENDPOINT_URL:?endpoint_url is required}"

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
case "$INPUT_ENDPOINT_URL" in
  https://?*) ;;
  *) printf 'endpoint_url must be an https URL\n' >&2; exit 2 ;;
esac

export AWS_ACCESS_KEY_ID="$INPUT_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$INPUT_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="$INPUT_REGION"
export AWS_EC2_METADATA_DISABLED=true
export AWS_PAGER=""
export AWS_ENDPOINT_URL="$INPUT_ENDPOINT_URL"
if [ -n "${INPUT_SESSION_TOKEN:-}" ]; then
  export AWS_SESSION_TOKEN="$INPUT_SESSION_TOKEN"
fi

exec aws s3 cp "$SOURCE" "s3://$INPUT_BUCKET/$INPUT_KEY" --only-show-errors
