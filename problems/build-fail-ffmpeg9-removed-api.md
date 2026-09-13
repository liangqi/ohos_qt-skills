---
id: problem-build-fail-ffmpeg9-removed-api-av-stream-get-codec-timebase
type: problem
domain: build
tags: [ffmpeg, api-change, ffmpeg9, av_stream_get_codec_timebase]
created: 2026-08-24
updated: 2026-08-24
status: solved
severity: medium
audience: public
refs: [semantic-qt-harmonyos-third-party-libs]
summary: >
  FFmpeg 9.x removed the av_stream_get_codec_timebase() function, so code using the old API fails to compile.
  Replace it with st->time_base (the stream time base), which is functionally equivalent.
leader_summary: >
  Captured a compatibility fix for the FFmpeg 9.x API.
impact: [Migration efficiency, Build troubleshooting]
deliverables: [problem record]
evidence: [QCTools builds successfully]
error_message: >
  error: use of undeclared identifier 'av_stream_get_codec_timebase'
error_code: ""
keywords: [ffmpeg, av_stream_get_codec_timebase, time_base, api-removal, ffmpeg9]
symptoms: An "undeclared identifier" error when compiling FFmpeg-related code
environment: FFmpeg 9.0.1 (Harmonybrew arm64_ohos), OHOS clang 15
---

# FFmpeg 9.x removed av_stream_get_codec_timebase

## Error message

```
error: use of undeclared identifier 'av_stream_get_codec_timebase'
```

## Scenario

QCTools uses `av_stream_get_codec_timebase(stream->stream())` to get the codec time base, but that function was removed in FFmpeg 9.0.1.

## Cause

FFmpeg 5+ removed the `AVStream->codec` field, which also made the codec time base returned by `av_stream_get_codec_timebase()` unavailable. The function was removed entirely in FFmpeg 9.x.

## Solution

Replace it with `stream->time_base` (the stream time base):

```cpp
// Old (FFmpeg < 9)
rational_to_string(av_stream_get_codec_timebase(stream->stream()), '/')

// New (FFmpeg 9.x)
rational_to_string(stream->stream()->time_base, '/')
```

The two return the same value in most cases.

## Notes

- Other FFmpeg API changes: `av_init_packet` is marked deprecated in 9.x (a warning, not an error)
- It's worth using `llvm-readelf --dyn-syms` to check that every UND symbol still exists in the new FFmpeg headers

## Results

| Field | Content |
|-------|---------|
| Leadership summary | FFmpeg 9.x API compatibility fix |
| Scope of impact | Qt OHOS applications using the old FFmpeg API |
| Deliverable | problem record |
| Evidence | QCTools builds successfully |
| How to reuse | When you hit "av_stream_get_codec_timebase undeclared", substitute directly |

## Related

- [[semantic-qt-harmonyos-third-party-libs]] — Guide to porting third-party libraries to HarmonyOS
