// ---- new tests without a new kit (since kit build 1 of this form): at the start the program reads one signed text file from the project's repo, the
// channel. It names the newest test pack per system (URL, size, SHA-256) and the newest program for each system. Nothing is used unless the Ed25519 signature fits
// the public key built into this program, so a changed file or a false server cannot make the kit run another DLL; a downloaded pack must also match the
// signed SHA-256. The channel's serial may never fall (no going back to an older signed file). The program never replaces itself: it says a new one exists.
// Channel layout: "fsr4-kit-channel 1" line, "key value" lines, last line "sig <128 hex>" over all bytes before it.
// Files beside the program: dlls-update.pack + dlls-update.txt (the signed channel file that names it), no-update.txt (the tester's off switch; empty is
// fine), update-seen.txt (the highest serial seen, and that the first-start note was shown). The record of finished runs is kept per user (StateDir), so
// it survives unpacking a new kit. FSR4_CHANNEL_URL points the check elsewhere for testing; the signature is still required.
#ifndef KIT_BUILD
#define KIT_BUILD 1      // the program's own number: the channel's program.<system>.build is compared with it
#endif
#ifndef KIT_PACK_SERIAL
#define KIT_PACK_SERIAL 0      // the serial of the pack that came in the kit's zip (dlls.pack.zst): 0 = none or unversioned
#endif
#ifndef KIT_PACK_VERSION
#define KIT_PACK_VERSION ""
#endif
#ifndef KIT_CHANNEL_URL
#define KIT_CHANNEL_URL "https://raw.githubusercontent.com/zgauthier2000/fsr4-shader-performance-overrides/main/timing-kit/channel/channel.txt"
#endif
#define CHANNEL_MAX (64u << 10)
struct Channel { char* text; long long serial, pack_serial, pack_size, pack_min, prog_build, prog_min, music_serial, music_size, music_min; char pack_ver[64], pack_url[512], pack_sha[65], prog_ver[64], prog_url[512], prog_note[512], pack_note[1024], message[1024], busy[1024], both[1024], passes[1024], music_ver[64], music_url[512], music_sha[65]; };

static void PrintPackNote(const char* note) {      // (2026-11-10) "pack.<os>.note": what the new tests measure; a literal \n in the signed value starts a new line
    if (!note[0]) return;
    printf("What the new tests measure:\n  ");
    for (const char* q = note; *q; q++) { if (q[0] == '\\' && q[1] == 'n') { printf("\n  "); q++; } else putchar((unsigned char)*q); }
    printf("\n\n");
}

static int HexVal(char c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : -1; }
static bool ChannelValue(const char* text, const char* key, char* out, size_t n) {      // the value of "key value" in the signed text
    const size_t kl = strlen(key);
    for (const char* l = text; l && *l; ) {
        const char* e = strchr(l, '\n');
        const size_t len = e ? (size_t)(e - l) : strlen(l);
        if (len > kl && !strncmp(l, key, kl) && l[kl] == ' ') {
            size_t v = len - kl - 1; if (v && l[kl + 1 + v - 1] == '\r') --v;
            if (v >= n) v = n - 1;
            memcpy(out, l + kl + 1, v); out[v] = 0;
            return true;
        }
        l = e ? e + 1 : NULL;
    }
    out[0] = 0; return false;
}
static bool ChannelCheck(const char* text, size_t n, const char* os, struct Channel* c) {      // true: the signature fits and the fields make sense
    memset(c, 0, sizeof(*c));
    if (n < 140 || n > CHANNEL_MAX || strlen(text) != n || strncmp(text, "fsr4-kit-channel 1\n", 19)) return false;
    const char* s = text + n; if (s[-1] == '\n') --s;
    if (s - text < 133 || strncmp(s - 132, "sig ", 4)) return false;
    const size_t body = (size_t)(s - 132 - text);
    unsigned char* sm = malloc(64 + body), *m = malloc(64 + body); unsigned long long ml = 0; bool ok = sm && m;
    for (int i = 0; ok && i < 64; ++i) { const int a = HexVal(s[-128 + 2 * i]), b = HexVal(s[-128 + 2 * i + 1]); ok = a >= 0 && b >= 0; if (ok) sm[i] = (unsigned char)(a * 16 + b); }
    if (ok) { memcpy(sm + 64, text, body); ok = crypto_sign_open(m, &ml, sm, 64 + body, KIT_SIGN_PUB) == 0; }
    free(sm); free(m);
    if (!ok) return false;
    char v[64], key[64];
    #define NUM(k, f) (ChannelValue(text, k, v, sizeof(v)) ? (c->f = atoll(v), true) : false)
    #define PK(k) (snprintf(key, sizeof(key), "pack.%s.%s", os, k), key)      // the two kits carry different DLL lists: one pack per system
    if (!NUM("serial", serial)) return false;
    NUM(PK("serial"), pack_serial); NUM(PK("size"), pack_size); NUM(PK("min_build"), pack_min); NUM("program.min_build", prog_min);
    ChannelValue(text, PK("version"), c->pack_ver, sizeof(c->pack_ver)); ChannelValue(text, PK("url"), c->pack_url, sizeof(c->pack_url)); ChannelValue(text, PK("sha256"), c->pack_sha, sizeof(c->pack_sha));
    ChannelValue(text, PK("busy"), c->busy, sizeof(c->busy)); ChannelValue(text, PK("both_times"), c->both, sizeof(c->both)); ChannelValue(text, PK("passes"), c->passes, sizeof(c->passes));
    ChannelValue(text, PK("note"), c->pack_note, sizeof(c->pack_note));      // (2026-11-10) a short text on what the pack's new tests measure; kits before this build ignore the key
    snprintf(key, sizeof(key), "program.%s.build", os); if (ChannelValue(text, key, v, sizeof(v))) c->prog_build = atoll(v);
    snprintf(key, sizeof(key), "program.%s.version", os); ChannelValue(text, key, c->prog_ver, sizeof(c->prog_ver));
    snprintf(key, sizeof(key), "program.%s.url", os); ChannelValue(text, key, c->prog_url, sizeof(c->prog_url));
    ChannelValue(text, "program.note", c->prog_note, sizeof(c->prog_note)); ChannelValue(text, "message", c->message, sizeof(c->message));
    NUM("music.serial", music_serial); NUM("music.size", music_size); NUM("music.min_build", music_min);      // (2026-11-06) the song pack, the same for both systems
    ChannelValue(text, "music.version", c->music_ver, sizeof(c->music_ver)); ChannelValue(text, "music.url", c->music_url, sizeof(c->music_url)); ChannelValue(text, "music.sha256", c->music_sha, sizeof(c->music_sha));
    #undef NUM
    #undef PK
    c->text = (char*)text;
    return true;
}
static void ChannelRules(const struct Channel* c) {      // what the program's slot rules take from the pack's channel file
    snprintf(chan_busy, sizeof(chan_busy), "%s", c->busy); snprintf(chan_both, sizeof(chan_both), "%s", c->both); snprintf(chan_passes, sizeof(chan_passes), "%s", c->passes);
}
// GET into memory (file NULL; at most max bytes) or into a file with a progress line. https, or http to this machine alone (tests).
static uint8_t* FetchUrl(const char* url, size_t max, const char* file, long long expect, size_t* got) {
    wchar_t wurl[640], host[256], path[512];
    if (!MultiByteToWideChar(CP_UTF8, 0, url, -1, wurl, 640)) return NULL;
    URL_COMPONENTSW u; memset(&u, 0, sizeof(u)); u.dwStructSize = sizeof(u); u.lpszHostName = host; u.dwHostNameLength = 256; u.lpszUrlPath = path; u.dwUrlPathLength = 512;
    if (!WinHttpCrackUrl(wurl, 0, 0, &u)) return NULL;
    const bool tls = u.nScheme == INTERNET_SCHEME_HTTPS;
    if (!tls && wcscmp(host, L"127.0.0.1") && wcscmp(host, L"localhost")) return NULL;
    uint8_t* buf = NULL; size_t len = 0, cap = 0; bool ok = false; FILE* o = NULL; ULONGLONG shown = 0;
    HINTERNET s = WinHttpOpen(L"fsr4-timing-kit", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (s) WinHttpSetTimeouts(s, 8000, 8000, 8000, file ? 60000 : 12000);
    HINTERNET c = s ? WinHttpConnect(s, host, u.nPort, 0) : NULL;
    HINTERNET r = c ? WinHttpOpenRequest(c, L"GET", path, NULL, WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, tls ? WINHTTP_FLAG_SECURE : 0) : NULL;
    if (r && WinHttpSendRequest(r, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) && WinHttpReceiveResponse(r, NULL)) {
        DWORD code = 0, cl = sizeof(code);
        WinHttpQueryHeaders(r, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER, NULL, &code, &cl, NULL);
        ok = code == 200;
        if (ok && file) { o = fopen(file, "wb"); ok = o != NULL; }
        static uint8_t chunk[1u << 18];
        for (DWORD avail = 0; ok && WinHttpQueryDataAvailable(r, &avail) && avail; ) {
            if (avail > sizeof(chunk)) avail = sizeof(chunk);
            if (len + avail > max) { ok = false; break; }
            DWORD n = 0;
            if (!WinHttpReadData(r, chunk, avail, &n)) { ok = false; break; }
            if (o) { if (fwrite(chunk, 1, n, o) != n) { ok = false; break; } }
            else {
                if (len + n + 1 > cap) { cap = (len + n + 1) * 2; uint8_t* nb = realloc(buf, cap); if (!nb) { ok = false; break; } buf = nb; }
                memcpy(buf + len, chunk, n);
            }
            len += n;
            if (o && GetTickCount64() - shown > 500) { shown = GetTickCount64(); printf("\r  %.1f of %.1f MB   ", len / 1e6, expect / 1e6); fflush(stdout); }
        }
        if (o) { printf("\r  %.1f of %.1f MB   \n", len / 1e6, expect / 1e6); if (fclose(o)) ok = false; }
    }
    if (r) WinHttpCloseHandle(r);
    if (c) WinHttpCloseHandle(c);
    if (s) WinHttpCloseHandle(s);
    if (!ok || !len) { free(buf); return NULL; }
    if (got) *got = len;
    if (file) return (uint8_t*)file;      // not NULL: done
    buf[len] = 0;
    return buf;
}
static char* ReadSmall(const char* name, size_t max, size_t* n) {
    FILE* f = fopen(name, "rb"); if (!f) return NULL;
    char* b = malloc(max + 1); size_t k = b ? fread(b, 1, max + 1, f) : 0; fclose(f);
    if (!b || k > max) { free(b); return NULL; }
    b[k] = 0; if (n) *n = k; return b;
}
static bool FileSha(const char* name, long long size, const char* want) {      // the file has this size and SHA-256
    FILE* f = fopen(name, "rb"); if (!f) return false;
    _fseeki64(f, 0, SEEK_END); const long long n = _ftelli64(f); _fseeki64(f, 0, SEEK_SET);
    bool ok = n == size && n > 0;
    uint8_t* b = ok ? malloc((size_t)n) : NULL; char hex[65] = "";
    ok = ok && b && fread(b, 1, (size_t)n, f) == (size_t)n && Sha256Hex(b, (size_t)n, hex) && !strcmp(hex, want);
    free(b); fclose(f); return ok;
}
// ---- the record of finished runs: lines "mode|tests version|ven:dev|date|report ID|sent 0/1|results file"; the last line of a run counts.
// The Linux kit's run.sh sets FSR4_STATE_DIR to a folder outside the kit (its Wine prefix goes with the kit folder).
static void StateFile(char* out, size_t n) {
    const char* d = getenv("FSR4_STATE_DIR"), *la = getenv("LOCALAPPDATA");
    char dir[MAX_PATH] = "";
    if (d && d[0]) snprintf(dir, sizeof(dir), "%s", d);
    else if (la && la[0]) { snprintf(dir, sizeof(dir), "%s\\FSR4 timing kit", la); CreateDirectoryA(dir, NULL); }
    snprintf(out, n, "%s%shistory.txt", dir, dir[0] ? "\\" : "");
}
static void HistoryAdd(const char* mode, const char* tests, unsigned ven, unsigned dev, const char* id, int sent, const char* results) {
    if (!tests[0]) return;
    char p[MAX_PATH + 32]; StateFile(p, sizeof(p));
    FILE* f = fopen(p, "a"); if (!f) return;
    SYSTEMTIME st; GetLocalTime(&st);
    fprintf(f, "%s|%s|%04x:%04x|%04d-%02d-%02d|%s|%d|%s\n", mode, tests, ven, dev, st.wYear, st.wMonth, st.wDay, id, sent, results);
    fclose(f);
}
struct Done { char date[16], id[32], results[MAX_PATH]; int sent; };
static bool HistoryFind(const char* mode, const char* tests, unsigned ven, unsigned dev, struct Done* d) {
    char p[MAX_PATH + 32], l[1024], want[128]; StateFile(p, sizeof(p));
    if (!tests[0]) return false;
    FILE* f = fopen(p, "r"); if (!f) return false;
    snprintf(want, sizeof(want), "%s|%s|%04x:%04x|", mode, tests, ven, dev);
    bool found = false;
    while (fgets(l, sizeof(l), f)) {
        if (strncmp(l, want, strlen(want))) continue;
        l[strcspn(l, "\r\n")] = 0;
        char* a = l + strlen(want), *b = strchr(a, '|'), *c = b ? strchr(b + 1, '|') : NULL, *e = c ? strchr(c + 1, '|') : NULL;
        if (!e) continue;
        *b = *c = *e = 0;
        memset(d, 0, sizeof(*d));
        snprintf(d->date, sizeof(d->date), "%s", a); snprintf(d->id, sizeof(d->id), "%s", b + 1); d->sent = atoi(c + 1); snprintf(d->results, sizeof(d->results), "%s", e + 1);
        found = true;
    }
    fclose(f);
    return found;
}
static bool AskYes(const char* q, bool dflt) {
    char in[16];
    printf("%s %s ", q, dflt ? "[Y/n]" : "[y/N]"); fflush(stdout);
    if (!fgets(in, sizeof(in), stdin) || in[0] == '\n' || in[0] == '\r') return dflt;
    return in[0] == 'y' || in[0] == 'Y';
}
static void WaitEnter(void) { char in[8]; printf("\nPress Enter to close."); fflush(stdout); fgets(in, sizeof(in), stdin); }
static char tests_version[64] = KIT_PACK_VERSION;
static bool night_wanted_flag = false, update_too_old = false, night_given = false;      // night_given: --all-nighter, or already agreed
static long long update_have = -1;
// The check at the start. Returns false when the program should close (the tester's answer, or a program too old for the current tests).
// check = false (--no-update, no-update.txt, --no-questions without --update): the network is not used; the newest verified pack here still counts.

// ---- new songs for the music player (2026-11-06, user: "i want this kit to also pull new songs via the same archive it grabs for the dlls (or a separate one)"):
// the signed channel can name a song pack (music.serial / version / url / size / sha256 [/ min_build]): a zip of NN_name.ogg files that replaces the songs in music\.
// The serial of the songs here is in music\serial.txt (the kit's own songs carry one). Only asked about when someone is there to answer; the download must match
// the signed checksum, and every file in it must be a plain .ogg name (no folders), at most 64 songs, 40 MB each, 300 MB in all, or nothing is changed.
static long long MusicSerialHere(void) { long long v = -1; FILE* f = fopen("music\\serial.txt", "r"); if (f) { if (fscanf(f, "%lld", &v) != 1) v = -1; fclose(f); } return v; }
static bool MusicNameOk(const char* n) {
    size_t L = strlen(n); if (L < 5 || L > 120 || _stricmp(n + L - 4, ".ogg")) return false;
    for (const char* c = n; *c; ++c) if (!(isalnum((unsigned char)*c) || *c == '_' || *c == '-' || *c == '.')) return false;
    return !strstr(n, "..");
}
static void MusicUpdate(const struct Channel* c, bool asks) {
    if (!asks || !c->music_url[0] || c->music_serial <= MusicSerialHere() || c->music_min > KIT_BUILD || c->music_size <= 0 || c->music_size > (300ll << 20)) return;
    char q[220]; snprintf(q, sizeof(q), "New songs for the music player are available (%s, %.0f MB). Download them?", c->music_ver, c->music_size / 1e6);
    if (!AskYes(q, true)) { printf("\n"); return; }
    printf("Downloading the new songs:\n");
    const bool dl = FetchUrl(c->music_url, (size_t)c->music_size + 1, "music-update.part", c->music_size, NULL) != NULL;
    if (!dl || !FileSha("music-update.part", c->music_size, c->music_sha)) { DeleteFileA("music-update.part"); printf(dl ? "The download doesn't match the signed checksum, so it was refused.\n\n" : "The download did not finish.\n\n"); return; }
    mz_zip_archive z; memset(&z, 0, sizeof(z)); bool ok = mz_zip_reader_init_file(&z, "music-update.part", 0); int n = ok ? (int)mz_zip_reader_get_num_files(&z) : 0; long long tot = 0;
    ok = ok && n > 0 && n <= 64;
    for (int i = 0; ok && i < n; ++i) { mz_zip_archive_file_stat st; ok = mz_zip_reader_file_stat(&z, (mz_uint)i, &st) && !st.m_is_directory && MusicNameOk(st.m_filename) && st.m_uncomp_size <= (40ull << 20); tot += ok ? (long long)st.m_uncomp_size : 0; }
    ok = ok && tot <= (300ll << 20);
    CreateDirectoryA("music", NULL); CreateDirectoryA("music\\new", NULL);
    for (int i = 0; ok && i < n; ++i) { mz_zip_archive_file_stat st; mz_zip_reader_file_stat(&z, (mz_uint)i, &st); char out[MAX_PATH]; snprintf(out, sizeof(out), "music\\new\\%s", st.m_filename); ok = mz_zip_reader_extract_to_file(&z, (mz_uint)i, out, 0); }
    if (n || ok) mz_zip_reader_end(&z);
    WIN32_FIND_DATAA fd; HANDLE h;
    if (ok) {                                                        // the old songs out, the new ones in
        h = FindFirstFileA("music\\*.ogg", &fd); if (h != INVALID_HANDLE_VALUE) { do { char d[MAX_PATH]; snprintf(d, sizeof(d), "music\\%s", fd.cFileName); DeleteFileA(d); } while (FindNextFileA(h, &fd)); FindClose(h); }
        h = FindFirstFileA("music\\new\\*.ogg", &fd); if (h != INVALID_HANDLE_VALUE) { do { char a[MAX_PATH], b[MAX_PATH]; snprintf(a, sizeof(a), "music\\new\\%s", fd.cFileName); snprintf(b, sizeof(b), "music\\%s", fd.cFileName); ok = MoveFileExA(a, b, MOVEFILE_REPLACE_EXISTING) && ok; } while (FindNextFileA(h, &fd)); FindClose(h); }
        FILE* f = fopen("music\\serial.txt", "w"); if (f) { fprintf(f, "%lld\n", c->music_serial); fclose(f); }
        printf(ok ? "Done: %d songs, checked against the project's signature.\n\n" : "Some of the new songs could not be put in place.\n\n", n);
    } else printf("The song pack could not be read, so the songs here were kept.\n\n");
    h = FindFirstFileA("music\\new\\*", &fd); if (h != INVALID_HANDLE_VALUE) { do { char d[MAX_PATH]; snprintf(d, sizeof(d), "music\\new\\%s", fd.cFileName); DeleteFileA(d); } while (FindNextFileA(h, &fd)); FindClose(h); }
    RemoveDirectoryA("music\\new"); DeleteFileA("music-update.part");
}
static bool UpdateStep(bool check, bool asks, const char* os, const char* mode, unsigned ven, unsigned dev, const char* gpu) {
    // what is here: the pack that came with the kit, and a downloaded one if its signed file and checksum still fit
    long long have = fopen_exists(PACK_NAME) ? KIT_PACK_SERIAL : -1;
    static struct Channel here; bool have_up = false; size_t n = 0;
    char* t = ReadSmall("dlls-update.txt", CHANNEL_MAX, &n);
    if (t && ChannelCheck(t, n, os, &here) && here.pack_serial > have && FileSha("dlls-update.pack", here.pack_size, here.pack_sha)) {
        have = here.pack_serial; have_up = true; pack_path = "dlls-update.pack"; ChannelRules(&here); snprintf(tests_version, sizeof(tests_version), "%s", here.pack_ver);
    }
    long long seen = 0; int noted = 0;
    { FILE* f = fopen("update-seen.txt", "r"); if (f) { if (fscanf(f, "%lld %d", &seen, &noted) != 2) { seen = 0; noted = 0; } fclose(f); } }
    bool checked = false, too_old = false;
    if (check) {
        if (!noted && asks) printf("This kit looks on the project's GitHub page for new tests each time it starts, so you don't need to download a new kit for them.\n"
                                   "That is an ordinary web request: nothing about you or your PC is sent. Downloads must carry the project's signature, or they are refused.\n"
                                   "To turn this off, start the program with --no-update, or put an empty file named no-update.txt beside it.\n\n");
        const char* env = getenv("FSR4_CHANNEL_URL");
        size_t cn = 0; char* ct = (char*)FetchUrl(env && env[0] ? env : KIT_CHANNEL_URL, CHANNEL_MAX, NULL, 0, &cn);
        static struct Channel c;
        if (!ct) printf("Could not reach the project's page to look for new tests%s.\n\n", have >= 0 ? "; using the tests already here" : "");
        else if (!ChannelCheck(ct, cn, os, &c)) printf("The new-tests file from the project's page has no valid signature, so it was ignored. Please tell the project about this.\n\n");
        else if (c.serial < seen) printf("The new-tests file from the project's page is older than one seen before, so it was ignored.\n\n");
        else {
            checked = true; seen = c.serial;
            if (c.message[0]) printf("From the project: %s\n\n", c.message);
            if (c.prog_build > KIT_BUILD) {
                too_old = c.prog_min > KIT_BUILD;
                static bool told; if (!told || too_old) printf("%s of the kit program is available (%s).\n%s%s%sDownload: %s\n\n", too_old ? "A new version is needed: this one can't run the current tests. The new version" : "A new version", c.prog_ver, c.prog_note, c.prog_note[0] ? "\n" : "", "", c.prog_url);
                told = true;
            }
            if (!too_old && c.pack_url[0] && c.pack_serial > have) {
                if (c.pack_min > KIT_BUILD) printf("New tests (%s) are out, but they need the newer kit program above.\n\n", c.pack_ver);
                else {
                    PrintPackNote(c.pack_note);
                    bool get = !asks && c.pack_size <= (1ll << 30);      // nobody to ask: no surprise of many GB
                    if (asks) { char q[200]; snprintf(q, sizeof(q), "New tests are available (%s, %.0f MB). Download them now?", c.pack_ver, c.pack_size / 1e6); get = AskYes(q, true); }
                    if (get) {
                        printf("Downloading the new tests:\n");
                        const bool dl = FetchUrl(c.pack_url, (size_t)c.pack_size + 1, "dlls-update.part", c.pack_size, NULL) != NULL;
                        if (dl && FileSha("dlls-update.part", c.pack_size, c.pack_sha)) {
                            pack_path = PACK_NAME;      // nothing has the old file open: the program reads a pack only when it needs one
                            FILE* o = fopen("dlls-update.tmp", "wb");
                            const bool wr = o && fwrite(ct, 1, cn, o) == cn; if (o) fclose(o);
                            if (wr && MoveFileExA("dlls-update.part", "dlls-update.pack", MOVEFILE_REPLACE_EXISTING) && MoveFileExA("dlls-update.tmp", "dlls-update.txt", MOVEFILE_REPLACE_EXISTING)) {
                                have = c.pack_serial; have_up = true; pack_path = "dlls-update.pack"; ChannelRules(&c); snprintf(tests_version, sizeof(tests_version), "%s", c.pack_ver);
                                printf("Done, checked against the project's signature.\n\n");
                            } else printf("Could not save the new tests in this folder.\n\n");
                        } else {
                            DeleteFileA("dlls-update.part");
                            printf(dl ? "The download doesn't match the signed checksum, so it was refused.\n\n" : "The download did not finish.\n\n");
                            if (have_up) pack_path = "dlls-update.pack";
                        }
                    }
                    if (have < c.pack_serial && have >= 0) printf("Carrying on with the tests already here (%s). A report from them is still useful.\n\n", tests_version[0] ? tests_version : "the kit's own");
                }
            }
        }
        if (checked && !too_old) MusicUpdate(&c, asks);      // (2026-11-06) new songs, if the channel names newer ones
        free(ct);      // (a kept channel lives in dlls-update.txt; rules were copied)
        if (c.text == ct) c.text = NULL;
    }
    { FILE* f = fopen("update-seen.txt", "w"); if (f) { fprintf(f, "%lld %d\n", seen, check ? 1 : noted); fclose(f); } }
    update_have = have;
    update_too_old = too_old;
    if (too_old) { if (asks) WaitEnter(); return false; }
    if (have < 0 && !DllsFolderHasAny()) {
        printf(asks ? "There are no tests here yet and they could not be downloaded. Please check the internet connection and start the kit again.\n" : "There are no tests here yet and they could not be downloaded. It tries again later.\n");
        if (asks) WaitEnter();
        return false;
    }
    struct Done d;
    if (asks && HistoryFind(mode, tests_version, ven, dev, &d)) {
        printf("Thank you! You already ran %s tests (%s) on this graphics card, %s, on %s (report %s).\n",
               checked ? "the latest" : "these", tests_version, gpu, d.date, d.id);
        if (d.sent) printf("Your report reached the project, and your help is a valued part of it.\n");
        else printf("That run's results were not sent. They are in %s: please post that file on the project's GitHub page or Discord if you can.\n", d.results);
        printf(checked ? "There is nothing new to test on this card right now. New tests will show up here when there are any, so please start the kit again another day.\n\n"
                       : "This kit could not look for newer tests just now, so there may be some: please try again when you are online.\n\n");
        if (!night_given && !strcmp(mode, "normal") && AskYes("Would you like to leave it running as an all-nighter? It repeats tests for cleaner figures while the PC is idle, and fetches new tests by itself.", false)) { night_wanted_flag = true; return true; }
        if (!AskYes("Run the same tests again anyway? (A repeat isn't needed.)", false)) { WaitEnter(); return false; }
        printf("\n");
    }
    return true;
}
// ---- the all-nighter: the program stays open, repeats the tests while this PC is idle until the figures are steady, fetches new signed tests by itself and
// sends results without asking (the tester agreed to all of it once, at the start of that session). Two levels: this loop (--all-nighter) looks for new tests and starts
// one measuring process at a time (--night-run), which runs rounds and exits with 0 (finished), 10 (new tests, or stopped) or 11 (time for a report in between).
// Its figures and report ID go on between processes (results-raw.txt, allnight.txt), so one report ID grows through a test pack's life.
// FSR4TIME_NIGHT_* are for testing: POLL (s), SEG (s), ROUNDS, TARGET (%), IDLE=0 (no idle checks), QUICK=1, TEST=1 (reports marked as tests);
// FSR4TIME_SENDFILE: write what would be sent to files with that prefix; FSR4TIME_BUSYFILE: while it exists the PC counts as in use; FSR4TIME_DISTURBFILE: the run
// finishing while it exists counts as disturbed, and the file is deleted. night-stop.txt beside the program ends everything cleanly.
#define NIGHT_POLL_S 1800      // look for new tests every 30 minutes (give or take five minutes per PC); user 2026-11-02
#define NIGHT_SEG_S (30 * 60)      // reports go out after the first round, then after a round once 30 minutes have passed: people may run it for only an hour or two
#define NIGHT_ROUNDS 24      // then the report goes out however noisy the card is; the file stays under what a report can carry
#define NIGHT_MIN_ROUNDS 4
#define NIGHT_TARGET 0.5      // % : standard error of a figure's mean, the worst of all sizes and scenes
static bool night_run = false, night_wanted = false;
static int night_exit = 0, night_rounds = 0; static char night_id[32] = "";
static long long have_serial = -1, night_seen_serial = 0;
static int EnvInt(const char* n, int d) { const char* v = getenv(n); return v && v[0] ? atoi(v) : d; }
static double CpuBusyShare(void) {      // since the last call: -1 the first time
    static ULONGLONG li, lk, lu; FILETIME i, k, u;
    if (!GetSystemTimes(&i, &k, &u)) return -1;
    #define Q(x) (((ULONGLONG)x.dwHighDateTime << 32) | x.dwLowDateTime)
    const ULONGLONG ci = Q(i), ck = Q(k), cu = Q(u); const bool first = !lk;
    const ULONGLONG di = ci - li, dt = (ck - lk) + (cu - lu);      // kernel time includes idle time
    #undef Q
    li = ci; lk = ck; lu = cu;
    return first || !dt ? -1 : 1.0 - (double)di / (double)dt;
}
static int GpuBusyLinux(void) {      // %, under Proton on AMD's Linux driver; -1: cannot tell
    int best = -1;
    for (int c = 0; c < 8; ++c) {
        char p[96]; snprintf(p, sizeof(p), "Z:\\sys\\class\\drm\\card%d\\device\\gpu_busy_percent", c);
        FILE* f = fopen(p, "r"); int v;
        if (f) { if (fscanf(f, "%d", &v) == 1 && v > best) best = v; fclose(f); }
    }
    return best;
}
#include <pdh.h>
static int GpuBusyWindows(void) {      // %, the busiest 3D or compute engine, from Windows' own counters; -1: cannot tell. Loaded by hand: the program must start without them
    HMODULE m = LoadLibraryA("pdh.dll"); if (!m) return -1;
    typedef LONG(WINAPI * Open)(LPCSTR, DWORD_PTR, PDH_HQUERY*); typedef LONG(WINAPI * Add)(PDH_HQUERY, LPCSTR, DWORD_PTR, PDH_HCOUNTER*); typedef LONG(WINAPI * Coll)(PDH_HQUERY);
    typedef LONG(WINAPI * Arr)(PDH_HCOUNTER, DWORD, LPDWORD, LPDWORD, PPDH_FMT_COUNTERVALUE_ITEM_A); typedef LONG(WINAPI * Close)(PDH_HQUERY);
    Open o = (Open)(void*)GetProcAddress(m, "PdhOpenQueryA"); Add a = (Add)(void*)GetProcAddress(m, "PdhAddEnglishCounterA"); Coll co = (Coll)(void*)GetProcAddress(m, "PdhCollectQueryData");
    Arr ar = (Arr)(void*)GetProcAddress(m, "PdhGetFormattedCounterArrayA"); Close cl = (Close)(void*)GetProcAddress(m, "PdhCloseQuery");
    PDH_HQUERY q = NULL; PDH_HCOUNTER h = NULL; int best = -1;
    if (o && a && co && ar && cl && o(NULL, 0, &q) == 0) {
        if (a(q, "\\GPU Engine(*)\\Utilization Percentage", 0, &h) == 0 && co(q) == 0) {
            Sleep(1000); co(q);
            DWORD size = 0, count = 0;
            ar(h, PDH_FMT_DOUBLE, &size, &count, NULL);
            PDH_FMT_COUNTERVALUE_ITEM_A* it = size ? malloc(size) : NULL;
            if (it && ar(h, PDH_FMT_DOUBLE, &size, &count, it) == 0) {
                best = 0;
                for (DWORD i = 0; i < count; ++i)
                    if ((strstr(it[i].szName, "engtype_3D") || strstr(it[i].szName, "engtype_Compute")) && it[i].FmtValue.CStatus == 0 && it[i].FmtValue.doubleValue > best) best = (int)it[i].FmtValue.doubleValue;
            }
            free(it);
        }
        cl(q);
    }
    FreeLibrary(m);
    return best;
}
static bool IsWine(void) { return GetProcAddress(GetModuleHandleA("ntdll.dll"), "wine_get_version") != NULL; }
static double SinceInput(void) {      // seconds; -1 where it says nothing (under Proton only the program's own windows would count)
    LASTINPUTINFO li = {.cbSize = sizeof(li)};
    return IsWine() || !GetLastInputInfo(&li) ? -1 : (double)(GetTickCount() - li.dwTime) / 1000.0;
}
static bool NightIdle(char* why, size_t n, bool print) {      // true: nothing else seems to be using this PC. Takes a few seconds.
    const char* bf = getenv("FSR4TIME_BUSYFILE");
    if (bf && fopen_exists(bf)) { snprintf(why, n, "this PC is in use (test file)"); return false; }
    if (!EnvInt("FSR4TIME_NIGHT_IDLE", 1)) return true;
    SYSTEM_POWER_STATUS ps; const bool bat = GetSystemPowerStatus(&ps) && ps.ACLineStatus == 0;
    const double in = SinceInput();
    CpuBusyShare(); Sleep(3000); const double cpu = CpuBusyShare();
    const int gpu = IsWine() ? GpuBusyLinux() : GpuBusyWindows();
    if (print) printf("on battery: %s; seconds since keyboard or mouse: %.0f (-1 = unknown here); processor busy: %.0f%%; graphics busy: %d%% (-1 = unknown here)\n", bat ? "yes" : "no", in, cpu * 100, gpu);
    if (bat) { snprintf(why, n, "on battery: please plug it in"); return false; }
    if (in >= 0 && in < 300) { snprintf(why, n, "someone is using this PC"); return false; }
    if (cpu > 0.25) { snprintf(why, n, "the processor is busy (%.0f%%)", cpu * 100); return false; }
    if (gpu > 10) { snprintf(why, n, "the graphics card is busy (%d%%)", gpu); return false; }
    return true;
}
static bool NightNewTests(const char* os) {      // the signed file names newer tests this program can run; looks at most once per poll
    static ULONGLONG last; const ULONGLONG now = GetTickCount64();
    const int poll = EnvInt("FSR4TIME_NIGHT_POLL", NIGHT_POLL_S);
    if (!last) last = now;
    if (now - last < (ULONGLONG)poll * 1000u) return false;
    last = now;
    const char* env = getenv("FSR4_CHANNEL_URL"); size_t cn = 0;
    char* ct = (char*)FetchUrl(env && env[0] ? env : KIT_CHANNEL_URL, CHANNEL_MAX, NULL, 0, &cn);
    static struct Channel c; bool yes = false;
    if (ct && ChannelCheck(ct, cn, os, &c) && c.serial >= night_seen_serial) yes = c.pack_url[0] && c.pack_serial > have_serial && c.pack_min <= KIT_BUILD;
    free(ct); c.text = NULL;
    return yes;
}
static bool NightStopAsked(void) { return fopen_exists("night-stop.txt"); }
// before each run: waits here while the PC is in use. False: leave the rounds (new tests, or stopped).
static bool NightGate(const char* os) {
    bool said = false;
    for (;;) {
        if (NightStopAsked() || NightNewTests(os)) return false;
        char why[128] = "";
        if (NightIdle(why, sizeof(why), false)) {
            if (said) { printf("Carrying on.\n"); fflush(stdout); }
            SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED);      // no sleep during a run; the screen may turn off
            return true;
        }
        SetThreadExecutionState(ES_CONTINUOUS);
        if (!said) { printf("Waiting: %s. It carries on by itself when the PC is idle.\n", why); fflush(stdout); said = true; }
        Sleep(EnvInt("FSR4TIME_NIGHT_IDLE", 1) ? 30000 : 1000);
    }
}
static bool NightDisturbed(ULONGLONG started) {      // the run that just ended: keep its figures?
    const char* df = getenv("FSR4TIME_DISTURBFILE");
    if (df && fopen_exists(df)) { DeleteFileA(df); return true; }
    if (!EnvInt("FSR4TIME_NIGHT_IDLE", 1)) return false;
    SYSTEM_POWER_STATUS ps; if (GetSystemPowerStatus(&ps) && ps.ACLineStatus == 0) return true;
    const double in = SinceInput();
    if (in >= 0 && in * 1000.0 < (double)(GetTickCount64() - started)) return true;
    return CpuBusyShare() > 0.6;      // the run itself takes a core or two
}
// per-pass timing: chan_passes (the signed channel file's pack.<os>.passes, a comma list) names the builds, default below; once per set of figures, after the first round, so a short session gets it too
#define PASSES_DEFAULT "lt1-reference,lt30-test,lt34-test,lt101-test,lt105-test,lt113-test,lt114-test,lt115-test,lt116-test,lt117-test,lt118-test"
static bool RunDll(const char* name, int inpack, const char* base, const char* raw, bool quick, const char* what);
static bool NightHasPasses(const char* raw) { FILE* f = fopen(raw, "r"); char l[64]; bool y = false; while (f && !y && fgets(l, sizeof(l), f)) y = l[0] == 'T' && l[1] == '|'; if (f) fclose(f); return y; }
static bool NightPasses(const char (*names)[64], int nd, const int* inpack, const char* base, const char* raw, bool quick, const char* os) {      // false: new tests or a stop request came first
    const char* want = getenv("FSR4_PASSLIST") && getenv("FSR4_PASSLIST")[0] ? getenv("FSR4_PASSLIST") : chan_passes[0] ? chan_passes : PASSES_DEFAULT;
    _putenv("FSR4TIME_PASSES=1");
    for (int j = 0; j < nd; ++j) {
        if (!InList(names[j], want, false)) continue;
        if (night_run && !NightGate(os)) { _putenv("FSR4TIME_PASSES="); return false; }
        RunDll(names[j], inpack[j], base, raw, quick, "(per-pass timing)");
    }
    _putenv("FSR4TIME_PASSES=");
    return true;
}
static void FileCut(const char* name, long long size) {
    HANDLE h = CreateFileA(name, GENERIC_WRITE, 0, NULL, OPEN_EXISTING, 0, NULL); if (h == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER p; p.QuadPart = size;
    if (SetFilePointerEx(h, p, NULL, FILE_BEGIN)) SetEndOfFile(h);
    CloseHandle(h);
}
static long long FileLen(const char* name) { WIN32_FILE_ATTRIBUTE_DATA a; return GetFileAttributesExA(name, GetFileExInfoStandard, &a) ? ((long long)a.nFileSizeHigh << 32) | a.nFileSizeLow : 0; }
static bool NightLoad(const char* tests, unsigned ven, unsigned dev, int* rounds, char* id, size_t idn, int* done) {      // what the last process left for these tests on this card
    FILE* f = fopen("allnight.txt", "r"); if (!f) return false;
    char t[80], i[32]; unsigned v, d; int r, dn; const int k = fscanf(f, "%79[^|]|%x:%x|%d|%31[^|]|%d", t, &v, &d, &r, i, &dn); fclose(f);
    if (k != 6 || strcmp(t, tests) || v != ven || d != dev) return false;
    *rounds = r; snprintf(id, idn, "%s", i); *done = dn;
    return true;
}
static void NightSave(const char* tests, unsigned ven, unsigned dev, int rounds, const char* id, int done) {
    FILE* f = fopen("allnight.txt", "w"); if (!f) return;
    fprintf(f, "%s|%04x:%04x|%d|%s|%d\n", tests, ven, dev, rounds, id, done); fclose(f);
}
static bool NightSteady(const char* raw, double* worst) {      // every figure known to within the target
    static struct Row rr[MAXROWS]; const int n = Collect(raw, rr, MAXROWS, NULL, 0, NULL, 0);
    const double target = EnvInt("FSR4TIME_NIGHT_TARGET", 0) > 0 ? EnvInt("FSR4TIME_NIGHT_TARGET", 0) : NIGHT_TARGET;
    double w = 0;
    for (int i = 0; i < n; ++i) {
        const int k = rr[i].n; const double m = Val(&rr[i]);
        if (k < 2 || m <= 0) { w = 100; continue; }
        double s = 0; for (int j = 0; j < k; ++j) s += (rr[i].runs[j] - m) * (rr[i].runs[j] - m);
        const double se = 100.0 * sqrt(s / (k - 1) / k) / m;
        if (se > w) w = se;
    }
    *worst = w;
    return n > 0 && w <= target;
}
static bool NightSend(const char* message, const char* n1, const char* t1, const char* n2, const char* t2) {
    const char* sf = getenv("FSR4TIME_SENDFILE");
    if (sf && sf[0]) {
        static int count; char p[MAX_PATH]; snprintf(p, sizeof(p), "%s%d-%lu.txt", sf, ++count, GetCurrentProcessId());
        FILE* f = fopen(p, "w"); if (!f) return false;
        fprintf(f, "MESSAGE %s\nFILE %s\n%sFILE %s\n%s", message, n1, t1, n2 ? n2 : "-", t2 ? t2 : ""); fclose(f); return true;
    }
    for (int a = 0; a < 3; ++a) { if (Send(message, n1, t1, n2, t2)) return true; Sleep(60000); }
    return false;
}
static bool NightConsent(void) {
    printf("\nAll-nighter mode. Leave this window open, and until you close it the kit will:\n"
           "  - repeat the tests while this PC is idle, until the figures are steady, then leave the graphics card alone;\n"
           "  - look for new tests every 30 minutes, and download and run them by itself (only ones with the project's signature);\n"
           "  - send each result to the project's results channel without asking: the same summary and per-run figures as after a normal run, no name.\n"
           "It stops for keyboard or mouse use (Windows only), other work on the processor or graphics card, and running on battery, and carries on afterwards. Its figures from a disturbed run are dropped.\n"
           "A desktop PC may use a lot of power during the rounds. Close the window at any time; finished rounds are kept.\n\n");
    return AskYes("Start the all-nighter?", false);
}
static int NightLoop(const char* os, unsigned ven, unsigned dev, const char* gpu) {
    char self[MAX_PATH]; GetModuleFileNameA(NULL, self, MAX_PATH);
    int crashes = 0;
    for (bool first = true;; first = false) {
        if (NightStopAsked()) return 0;
        SYSTEMTIME st; GetLocalTime(&st);
        printf("\n[%02d:%02d] Looking for new tests.\n", st.wHour, st.wMinute); fflush(stdout);
        const bool ok = UpdateStep(true, false, os, "normal", ven, dev, gpu);
        if (update_too_old) { WaitEnter(); return 0; }
        const int poll = EnvInt("FSR4TIME_NIGHT_POLL", NIGHT_POLL_S);
        const int jitter = poll > 600 ? (int)(GetTickCount64() % 600) - 300 : 0;
        int rounds = 0, done = 0; char id[32];
        const char* tests = tests_version[0] ? tests_version : KIT_VERSION;
        if (ok && !(NightLoad(tests, ven, dev, &rounds, id, sizeof(id), &done) && done)) {
            char cmd[MAX_PATH + 64]; snprintf(cmd, sizeof(cmd), "\"%s\" --night-run", self);
            STARTUPINFOA si = {.cb = sizeof(si)}; PROCESS_INFORMATION pi; DWORD code = 1;
            if (CreateProcessA(NULL, cmd, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) {
                WaitForSingleObject(pi.hProcess, INFINITE); GetExitCodeProcess(pi.hProcess, &code); CloseHandle(pi.hProcess); CloseHandle(pi.hThread);
            }
            if (code == 0 || code == 10 || code == 11) { crashes = 0; if (code) continue; }
            else if (++crashes >= 3) { printf("The test process stopped unexpectedly three times, so the all-nighter is ending. Please tell the project.\n"); WaitEnter(); return 1; }
            else continue;
            if (NightLoad(tests, ven, dev, &rounds, id, sizeof(id), &done) && done) printf("\nThank you! All of these tests (%s) are done on this card (report %s).\n", tests, id);
        } else if (ok && first) printf("All of these tests (%s) are already done on this card by an all-nighter. Thank you!\n", tests);
        printf("The graphics card is idle now. The kit looks for new tests every 30 minutes; you can close this window at any time.\n"); fflush(stdout);
        for (int s = 0; s < poll + jitter && !NightStopAsked(); ++s) Sleep(1000);
    }
}
