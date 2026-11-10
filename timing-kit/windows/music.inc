// music.inc (2026-11-06, user: "include an .ogg file of public domain music" ... "the space bar starts playing music, and the left and right arrows are skip tracks
// forward and back. pressing space again should pause it"): optional music while the timing runs go. The songs are music\*.ogg beside the program, played in name
// order (NN_name.ogg). Off until the tester presses Space; Space again pauses, again resumes. Right / Left arrow: next / previous song (wraps). The first Space starts
// a random song; a song that ends goes on to the next one. Keys are read only between MusicBegin and MusicEnd (the timing runs), never while the program asks a
// question, and the console's input is flushed afterwards so no key pressed for the music answers one. Decoder: stb_vorbis (public domain / MIT, stb\stb_vorbis.c).
// Sound: winmm waveOut, which Wine / Proton also provide. A report says whether music played (its timings were taken with it on).
#include <ctype.h>
#define STB_VORBIS_HEADER_ONLY
#include "stb/stb_vorbis.c"
#include <mmsystem.h>
#define MUSIC_MAX 64
#define MUSIC_BUFS 4
#define MUSIC_FRAMES 8192
static char music_files[MUSIC_MAX][MAX_PATH]; static int music_n = 0;
static volatile LONG music_req = 0;          // 1 toggle, 2 next, 3 previous, 9 quit
static volatile LONG music_keys_on = 0;
static bool music_played = false;
static HANDLE music_thread = NULL, music_keys_thread = NULL, music_wake = NULL; static DWORD music_mode0 = 0; static bool music_mode_set = false;
// (2026-11-10) Lyrics: a song may carry its timed lines in a Vorbis comment LYRICS= ("[mm:ss.cc]text" per line, LRC style); while it plays (not paused) the header's
// joke row shows the line being sung (fsr4time.c HeaderJoke), from the sound device's own play position; the jokes come back between songs, when paused and for songs without.
#define LYR_MAX 400
static double lyr_t[LYR_MAX]; static char lyr_s[LYR_MAX][128]; static int lyr_n = 0, lyr_cur = -2;
static void LyricSet(const char* t) {
    EnterCriticalSection(&lyric_cs); snprintf(lyric_now, sizeof(lyric_now), "%s", t ? t : ""); LeaveCriticalSection(&lyric_cs);
    InterlockedIncrement(&lyric_seq);
    if (getenv("FSR4TIME_LYRICLOG")) { printf("[lyric] %s\n", t && t[0] ? t : "(none)"); fflush(stdout); }      // test only: each change also in the output
}
static void LyricsLoad(stb_vorbis* v) {      // the LYRICS= comment of the song just opened
    lyr_n = 0; lyr_cur = -2; LyricSet("");
    stb_vorbis_comment c = stb_vorbis_get_comment(v);
    for (int i = 0; i < c.comment_list_length; ++i) {
        const char* e = c.comment_list[i];
        if (_strnicmp(e, "LYRICS=", 7)) continue;
        for (const char* l = e + 7; *l && lyr_n < LYR_MAX; ) {
            const char* nl = strchr(l, '\n'); const size_t len = nl ? (size_t)(nl - l) : strlen(l);
            int mm = 0, ss = 0, cc = 0, used = 0;
            if (len > 9 && sscanf(l, "[%d:%d.%d]%n", &mm, &ss, &cc, &used) == 3 && used > 0 && (size_t)used <= len) {
                size_t k = len - (size_t)used; if (k && l[used + k - 1] == '\r') --k; if (k > sizeof(lyr_s[0]) - 1) k = sizeof(lyr_s[0]) - 1;
                lyr_t[lyr_n] = mm * 60.0 + ss + cc / 100.0; memcpy(lyr_s[lyr_n], l + used, k); lyr_s[lyr_n][k] = 0;
                for (char* q = lyr_s[lyr_n]; *q; ++q) if ((unsigned char)*q < 32 || (unsigned char)*q > 126) *q = ' ';      // the console row takes plain characters only
                ++lyr_n;
            }
            l = nl ? nl + 1 : l + len;
        }
        break;
    }
}
static void LyricsTick(HWAVEOUT wo, int ch, int rate, bool paused) {      // the line for the device's play position
    int want = -1;
    if (lyr_n && wo && !paused) {
        MMTIME mt = {.wType = TIME_SAMPLES};
        if (waveOutGetPosition(wo, &mt, sizeof(mt)) == MMSYSERR_NOERROR) {
            const double s = mt.wType == TIME_SAMPLES ? (double)mt.u.sample / rate : mt.wType == TIME_BYTES ? (double)mt.u.cb / (rate * ch * 2) : -1;
            for (int i = 0; i < lyr_n && s >= 0 && lyr_t[i] <= s + 0.05; ++i) want = i;
        }
    }
    if (want != lyr_cur) { lyr_cur = want; LyricSet(want >= 0 ? lyr_s[want] : ""); }
}
static void MusicTitle(const char* path, char* out, size_t n) {
    const char* b = strrchr(path, '\\'); b = b ? b + 1 : path;
    if (isdigit((unsigned char)b[0]) && isdigit((unsigned char)b[1]) && b[2] == '_') b += 3;
    snprintf(out, n, "%s", b); char* d = strrchr(out, '.'); if (d) *d = 0;
    for (char* c = out; *c; ++c) if (*c == '_') *c = ' ';
    for (char* c = out; *c; ++c) if (c == out || c[-1] == ' ') *c = (char)toupper((unsigned char)*c);      // Title Case for the screen
}
static void MusicShow(int cur, bool playing, bool paused) {      // the header's music row (fsr4time.c HeaderMusic); also the only place the keys are shown
    char t[MAX_PATH] = ""; if (cur >= 0) MusicTitle(music_files[cur], t, sizeof(t));
    if (!playing) snprintf(music_status, sizeof(music_status), "Music: off   [Space] play   [<-] [->] skip   (%d songs)", music_n);
    else snprintf(music_status, sizeof(music_status), "Music: %s %d/%d  %s   [Space] %s   [<-] [->] skip", paused ? "paused" : "playing", cur + 1, music_n, t, paused ? "resume" : "pause");
    const char* st = strstr(t, " - "); st = st ? st + 3 : t;      // (2026-11-10) narrow windows: the title without "Artist - "
    if (!playing) music_status_short[0] = 0;
    else snprintf(music_status_short, sizeof(music_status_short), "Music: %s %d/%d  %s   [Space] %s   [<-] [->] skip", paused ? "paused" : "playing", cur + 1, music_n, st, paused ? "resume" : "pause");
}
static int MusicCmp(const void* a, const void* b) { return strcmp((const char*)a, (const char*)b); }
static int MusicScan(void) {
    WIN32_FIND_DATAA fd; HANDLE f = FindFirstFileA("music\\*.ogg", &fd); music_n = 0;
    if (f == INVALID_HANDLE_VALUE) return 0;
    do { if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) && music_n < MUSIC_MAX) snprintf(music_files[music_n++], MAX_PATH, "music\\%s", fd.cFileName); } while (FindNextFileA(f, &fd));
    FindClose(f); qsort(music_files, music_n, MAX_PATH, MusicCmp); return music_n;
}
static DWORD WINAPI MusicMain(LPVOID unused) {
    (void)unused;
    HWAVEOUT wo = NULL; WAVEHDR hdr[MUSIC_BUFS]; static short pcm[MUSIC_BUFS][MUSIC_FRAMES * 2];
    stb_vorbis* v = NULL; int cur = -1, ch = 2, rate = 44100; bool playing = false, paused = false, eof = false;
    HANDLE done = CreateEventA(NULL, FALSE, FALSE, NULL);
    for (;;) {
        LONG r = InterlockedExchange(&music_req, 0);
        if (r == 9) break;
        int jump = 0;
        if (r == 1) {
            if (!playing) { srand((unsigned)GetTickCount64()); jump = 1; cur = rand() % music_n - 1; }      // first press: a random song
            else if (!paused) { waveOutPause(wo); paused = true; MusicShow(cur, playing, paused); printf("[music paused]\n"); fflush(stdout); }
            else { waveOutRestart(wo); paused = false; MusicShow(cur, playing, paused); printf("[music playing]\n"); fflush(stdout); }
        } else if ((r == 2 || r == 3) && playing) jump = r == 2 ? 1 : -1;
        for (int tries = 0; jump && tries < music_n; ++tries) {        // open the next / previous song that decodes
            if (wo) { waveOutReset(wo); for (int b = 0; b < MUSIC_BUFS; ++b) waveOutUnprepareHeader(wo, &hdr[b], sizeof(WAVEHDR)); waveOutClose(wo); wo = NULL; }
            if (v) { stb_vorbis_close(v); v = NULL; }
            cur = ((cur + jump) % music_n + music_n) % music_n; int err = 0;
            v = stb_vorbis_open_filename(music_files[cur], &err, NULL);
            if (!v) continue;
            stb_vorbis_info in = stb_vorbis_get_info(v); ch = in.channels > 2 ? 2 : in.channels; rate = (int)in.sample_rate;
            WAVEFORMATEX wf = {.wFormatTag = WAVE_FORMAT_PCM, .nChannels = (WORD)ch, .nSamplesPerSec = (DWORD)rate, .wBitsPerSample = 16};
            wf.nBlockAlign = (WORD)(ch * 2); wf.nAvgBytesPerSec = (DWORD)rate * wf.nBlockAlign;
            if (waveOutOpen(&wo, WAVE_MAPPER, &wf, (DWORD_PTR)done, 0, CALLBACK_EVENT) != MMSYSERR_NOERROR) { wo = NULL; stb_vorbis_close(v); v = NULL; printf("[music: no sound device]\n"); fflush(stdout); break; }
            for (int b = 0; b < MUSIC_BUFS; ++b) { memset(&hdr[b], 0, sizeof(WAVEHDR)); hdr[b].lpData = (LPSTR)pcm[b]; hdr[b].dwFlags = WHDR_DONE; }
            playing = true; paused = false; eof = false; music_played = true; jump = 0;
            LyricsLoad(v);
            char t[MAX_PATH]; MusicTitle(music_files[cur], t, sizeof(t)); MusicShow(cur, playing, paused); printf("[music: %s]\n", t); fflush(stdout);
        }
        if (playing && wo && v && !paused) {                              // keep the buffers full
            for (int b = 0; b < MUSIC_BUFS; ++b) if (hdr[b].dwFlags & WHDR_DONE) {
                if (hdr[b].dwFlags & WHDR_PREPARED) waveOutUnprepareHeader(wo, &hdr[b], sizeof(WAVEHDR));
                if (eof) continue;
                int got = stb_vorbis_get_samples_short_interleaved(v, ch, pcm[b], MUSIC_FRAMES * ch);
                if (got <= 0) { eof = true; continue; }
                hdr[b].dwBufferLength = (DWORD)(got * ch * 2); hdr[b].dwFlags = 0;
                waveOutPrepareHeader(wo, &hdr[b], sizeof(WAVEHDR)); waveOutWrite(wo, &hdr[b], sizeof(WAVEHDR));
            }
        }
        if (playing) LyricsTick(wo, ch, rate, paused);
        if (playing && eof) {                                              // the song ended and its last buffer played: the next one
            bool all = true; for (int b = 0; b < MUSIC_BUFS; ++b) all = all && (hdr[b].dwFlags & WHDR_DONE);
            if (all) InterlockedCompareExchange(&music_req, 2, 0);
        }
        HANDLE w[2] = {done, music_wake}; WaitForMultipleObjects(2, w, FALSE, 100);
    }
    LyricSet("");
    if (wo) { waveOutReset(wo); for (int b = 0; b < MUSIC_BUFS; ++b) waveOutUnprepareHeader(wo, &hdr[b], sizeof(WAVEHDR)); waveOutClose(wo); }
    if (v) stb_vorbis_close(v);
    CloseHandle(done); return 0;
}
static DWORD WINAPI MusicKeys(LPVOID in_) {
    // (2026-11-06) a blocking read: under Proton in a Linux terminal, waiting on the console handle never signals, so keys were never seen. MusicEnd wakes the
    // read with a made-up key (VK_F24) before it stops the thread.
    HANDLE in = (HANDLE)in_;
    while (music_keys_on) {
        INPUT_RECORD ev[16]; DWORD n = 0;
        if (!ReadConsoleInputW(in, ev, 16, &n)) { Sleep(100); continue; }
        for (DWORD i = 0; i < n; ++i) {
            if (ev[i].EventType != KEY_EVENT || !ev[i].Event.KeyEvent.bKeyDown) continue;
            const WORD k = ev[i].Event.KeyEvent.wVirtualKeyCode; const WCHAR ch = ev[i].Event.KeyEvent.uChar.UnicodeChar;
            LONG r = (k == VK_SPACE || ch == L' ') ? 1 : k == VK_RIGHT ? 2 : k == VK_LEFT ? 3 : 0;
            if (r) { InterlockedExchange(&music_req, r); SetEvent(music_wake); }
        }
    }
    return 0;
}
// Called once the questions are over and before the first timing run; nothing happens without music\*.ogg or without a console to read keys from
// (an all-nighter, a run started by a script, --no-music).
static void MusicBegin(bool no_music) {
    if (no_music || getenv("FSR4TIME_NOMUSIC") || !MusicScan()) return;
    HANDLE in = GetStdHandle(STD_INPUT_HANDLE); DWORD mode = 0;
    if (in == INVALID_HANDLE_VALUE || !GetConsoleMode(in, &mode)) return;
    // (2026-11-06, user: "space doesn't do anything") the console in its usual line mode: in a Linux terminal under Proton the keys then wait for Enter and never arrive
    // as key events. Single keys during the runs, without echo; the old mode comes back in MusicEnd.
    music_mode0 = mode; music_mode_set = SetConsoleMode(in, (mode & ~(DWORD)(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT)) | ENABLE_PROCESSED_INPUT);
    FlushConsoleInputBuffer(in);
    InitializeCriticalSection(&lyric_cs);
    music_wake = CreateEventA(NULL, FALSE, FALSE, NULL); music_keys_on = 1;
    music_thread = CreateThread(NULL, 0, MusicMain, NULL, 0, NULL); SetThreadPriority(music_thread, THREAD_PRIORITY_BELOW_NORMAL);
    music_keys_thread = CreateThread(NULL, 0, MusicKeys, in, 0, NULL);
    MusicShow(-1, false, false);      // the header row shows it from now on
    printf("Music while it runs (%d songs, off until you press a key): Space plays / pauses, Left / Right arrows skip.\n\n", music_n); fflush(stdout);
    if (getenv("FSR4TIME_MUSICTEST")) { InterlockedExchange(&music_req, 1); SetEvent(music_wake); }      // test: start playing at once
}
static void MusicEnd(void) {
    if (!music_thread) return;
    music_keys_on = 0;
    { INPUT_RECORD w = {.EventType = KEY_EVENT}; w.Event.KeyEvent.bKeyDown = TRUE; w.Event.KeyEvent.wVirtualKeyCode = VK_F24; w.Event.KeyEvent.wRepeatCount = 1; DWORD k = 0;
      WriteConsoleInputW(GetStdHandle(STD_INPUT_HANDLE), &w, 1, &k); }      // wakes the blocking read
    if (WaitForSingleObject(music_keys_thread, 2000) == WAIT_TIMEOUT) TerminateThread(music_keys_thread, 0);
    InterlockedExchange(&music_req, 9); SetEvent(music_wake); WaitForSingleObject(music_thread, 3000);
    CloseHandle(music_thread); CloseHandle(music_keys_thread); CloseHandle(music_wake); music_thread = NULL;
    music_status[0] = 0;      // the header's music row goes blank again (the header ends right after)
    FlushConsoleInputBuffer(GetStdHandle(STD_INPUT_HANDLE));
    if (music_mode_set) SetConsoleMode(GetStdHandle(STD_INPUT_HANDLE), music_mode0);
}
