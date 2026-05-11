/*
 * Nexa native runtime (Win64).
 *
 * Linked into every Nexa executable produced by `--build`. Exposes the
 * `nx_*` symbols that the generated x86-64 assembly calls into, plus the
 * C `main` shim that bootstraps into the user-defined `nx_user_main`.
 *
 * All Nexa scalar values are passed as 64-bit signed integers (long long).
 * Heap-allocated objects (arrays, structs) are returned as pointers stored
 * inside those 64-bit slots.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <ctype.h>

extern long long nx_user_main(void);
void nx_panic(const char* msg);
void* nx_alloc(long long n);

void nx_print_i32(long long v) {
    printf("%lld\n", v);
    fflush(stdout);
}

void nx_print_f64(double v) {
    /* %g matches Python's str(float) closely for the common cases used
     * in tests (no trailing zeros, no scientific notation for ordinary
     * magnitudes). */
    printf("%g\n", v);
    fflush(stdout);
}

void nx_print_str(const char* v) {
    printf("%s\n", v ? v : "(null)");
    fflush(stdout);
}

long long nx_read_i32(void) {
    long long v = 0;
    if (scanf("%lld", &v) != 1) {
        nx_panic("read_i32 failed");
    }
    return v;
}

double nx_read_f64(void) {
    double v = 0.0;
    if (scanf("%lf", &v) != 1) {
        nx_panic("read_f64 failed");
    }
    return v;
}

char* nx_read_str(void) {
    char buf[4096];
    if (scanf("%4095s", buf) != 1) {
        nx_panic("read_str failed");
    }
    size_t n = strlen(buf);
    char* out = (char*)nx_alloc((long long)n + 1);
    memcpy(out, buf, n + 1);
    return out;
}

long long nx_array_len(long long arr) {
    long long* p = (long long*)(intptr_t)arr;
    if (!p) nx_panic("len on null array");
    return p[0];
}

long long nx_str_len(const char* s) {
    return s ? (long long)strlen(s) : 0;
}

char* nx_str_clone(const char* s) {
    if (!s) s = "";
    size_t n = strlen(s);
    char* out = (char*)nx_alloc((long long)n + 1);
    memcpy(out, s, n + 1);
    return out;
}

char* nx_str_cat(const char* a, const char* b) {
    if (!a) a = "";
    if (!b) b = "";
    size_t na = strlen(a), nb = strlen(b);
    char* out = (char*)nx_alloc((long long)(na + nb + 1));
    memcpy(out, a, na);
    memcpy(out + na, b, nb + 1);
    return out;
}

char* nx_substr(const char* s, long long start, long long count) {
    if (!s) s = "";
    size_t n = strlen(s);
    if (start < 0) start = 0;
    if (count < 0) count = 0;
    size_t pos = (size_t)start;
    if (pos > n) pos = n;
    size_t take = (size_t)count;
    if (take > n - pos) take = n - pos;
    char* out = (char*)nx_alloc((long long)take + 1);
    memcpy(out, s + pos, take);
    out[take] = '\0';
    return out;
}

long long nx_find(const char* haystack, const char* needle) {
    if (!haystack) haystack = "";
    if (!needle) needle = "";
    char* p = strstr(haystack, needle);
    return p ? (long long)(p - haystack) : -1;
}

long long nx_contains(const char* haystack, const char* needle) {
    return nx_find(haystack, needle) >= 0 ? 1 : 0;
}

long long nx_starts_with(const char* s, const char* prefix) {
    if (!s) s = "";
    if (!prefix) prefix = "";
    size_t n = strlen(prefix);
    return strncmp(s, prefix, n) == 0 ? 1 : 0;
}

long long nx_ends_with(const char* s, const char* suffix) {
    if (!s) s = "";
    if (!suffix) suffix = "";
    size_t ns = strlen(s), nt = strlen(suffix);
    if (nt > ns) return 0;
    return strcmp(s + ns - nt, suffix) == 0 ? 1 : 0;
}

char* nx_replace(const char* s, const char* old, const char* repl) {
    if (!s) s = "";
    if (!old) old = "";
    if (!repl) repl = "";
    size_t ns = strlen(s), no = strlen(old), nr = strlen(repl);
    if (no == 0) return nx_str_clone(s);
    size_t hits = 0;
    const char* p = s;
    while ((p = strstr(p, old)) != NULL) {
        hits++;
        p += no;
    }
    size_t out_n = ns + (nr >= no ? hits * (nr - no) : 0);
    if (nr < no) {
        out_n = ns - hits * (no - nr);
    }
    char* out = (char*)nx_alloc((long long)out_n + 1);
    char* w = out;
    p = s;
    const char* q;
    while ((q = strstr(p, old)) != NULL) {
        size_t chunk = (size_t)(q - p);
        memcpy(w, p, chunk);
        w += chunk;
        memcpy(w, repl, nr);
        w += nr;
        p = q + no;
    }
    strcpy(w, p);
    return out;
}

char* nx_str_remove(const char* s, const char* needle) {
    return nx_replace(s, needle, "");
}

char* nx_trim(const char* s) {
    if (!s) s = "";
    const char* a = s;
    while (*a && isspace((unsigned char)*a)) a++;
    const char* b = s + strlen(s);
    while (b > a && isspace((unsigned char)b[-1])) b--;
    size_t n = (size_t)(b - a);
    char* out = (char*)nx_alloc((long long)n + 1);
    memcpy(out, a, n);
    out[n] = '\0';
    return out;
}

char* nx_lower(const char* s) {
    char* out = nx_str_clone(s);
    for (char* p = out; *p; ++p) *p = (char)tolower((unsigned char)*p);
    return out;
}

char* nx_upper(const char* s) {
    char* out = nx_str_clone(s);
    for (char* p = out; *p; ++p) *p = (char)toupper((unsigned char)*p);
    return out;
}

long long nx_ord(const char* s) {
    return (s && *s) ? (unsigned char)*s : 0;
}

char* nx_chr(long long v) {
    char* out = (char*)nx_alloc(2);
    out[0] = (char)v;
    out[1] = '\0';
    return out;
}

long long nx_parse_i32(const char* s) {
    return s ? strtoll(s, NULL, 10) : 0;
}

double nx_parse_f64(const char* s) {
    return s ? strtod(s, NULL) : 0.0;
}

char* nx_to_str_i64(long long v) {
    char buf[64];
    snprintf(buf, sizeof(buf), "%lld", v);
    return nx_str_clone(buf);
}

char* nx_to_str_f64(double v) {
    char buf[128];
    snprintf(buf, sizeof(buf), "%g", v);
    return nx_str_clone(buf);
}

long long nx_to_i32_i64(long long v) {
    return v;
}

long long nx_to_i32_f64(double v) {
    return (long long)v;
}

long long nx_to_i32_str(const char* s) {
    return nx_parse_i32(s);
}

double nx_to_f64_i64(long long v) {
    return (double)v;
}

double nx_to_f64_f64(double v) {
    return v;
}

double nx_to_f64_str(const char* s) {
    return nx_parse_f64(s);
}

long long nx_to_bool_i64(long long v) {
    return v != 0 ? 1 : 0;
}

long long nx_to_bool_f64(double v) {
    return v != 0.0 ? 1 : 0;
}

long long nx_to_bool_str(const char* s) {
    if (!s || !*s) return 0;
    if (strcmp(s, "0") == 0 || strcmp(s, "false") == 0 || strcmp(s, "False") == 0) return 0;
    return 1;
}

long long nx_abs_i64(long long v) {
    return v < 0 ? -v : v;
}

double nx_abs_f64(double v) {
    return v < 0.0 ? -v : v;
}

long long nx_min_i64(long long a, long long b) {
    return a < b ? a : b;
}

long long nx_max_i64(long long a, long long b) {
    return a > b ? a : b;
}

double nx_min_f64(double a, double b) {
    return a < b ? a : b;
}

double nx_max_f64(double a, double b) {
    return a > b ? a : b;
}

char* nx_min_str(const char* a, const char* b) {
    if (!a) a = "";
    if (!b) b = "";
    return nx_str_clone(strcmp(a, b) <= 0 ? a : b);
}

char* nx_max_str(const char* a, const char* b) {
    if (!a) a = "";
    if (!b) b = "";
    return nx_str_clone(strcmp(a, b) >= 0 ? a : b);
}

long long nx_rand(void) {
    return (long long)rand();
}

void nx_srand(long long seed) {
    srand((unsigned int)seed);
}

long long nx_rand_range(long long lo, long long hi) {
    if (hi < lo) {
        long long tmp = lo;
        lo = hi;
        hi = tmp;
    }
    long long span = hi - lo + 1;
    if (span <= 0) return lo;
    return lo + (rand() % span);
}

long long nx_time(void) {
    return (long long)time(NULL);
}

long long nx_clock(void) {
    return (long long)clock();
}

void nx_panic(const char* msg) {
    fprintf(stderr, "panic: %s\n", msg ? msg : "(null)");
    fflush(stderr);
    exit(1);
}

void* nx_alloc(long long n) {
    if (n < 0) {
        nx_panic("nx_alloc: negative size");
    }
    void* p = calloc(1, (size_t)n);
    if (!p) {
        nx_panic("nx_alloc: out of memory");
    }
    return p;
}

/*
 * Concurrency primitives: native build keeps single-threaded semantics
 * to mirror the deterministic teaching model. `chan` is implemented as
 * a tiny FIFO ring; `spawn` is currently sequential (not exposed by the
 * native scope confirmed with the user). These exist so generated code
 * can still link if the front end emits CALL nodes targeting them.
 */
typedef struct nx_chan {
    long long cap;
    long long head;
    long long tail;
    long long count;
    long long* buf;
} nx_chan;

long long nx_chan_new(long long cap) {
    if (cap < 1) cap = 1;
    nx_chan* c = (nx_chan*)nx_alloc((long long)sizeof(nx_chan));
    c->cap = cap;
    c->buf = (long long*)nx_alloc(cap * (long long)sizeof(long long));
    return (long long)(intptr_t)c;
}

void nx_chan_send(long long ch, long long v) {
    nx_chan* c = (nx_chan*)(intptr_t)ch;
    if (!c) nx_panic("send on null channel");
    if (c->count >= c->cap) nx_panic("send on full channel (single-threaded native runtime)");
    c->buf[c->tail] = v;
    c->tail = (c->tail + 1) % c->cap;
    c->count += 1;
}

long long nx_chan_recv(long long ch) {
    nx_chan* c = (nx_chan*)(intptr_t)ch;
    if (!c) nx_panic("recv on null channel");
    if (c->count == 0) nx_panic("recv on empty channel (single-threaded native runtime)");
    long long v = c->buf[c->head];
    c->head = (c->head + 1) % c->cap;
    c->count -= 1;
    return v;
}

long long nx_chan_ready(long long ch) {
    nx_chan* c = (nx_chan*)(intptr_t)ch;
    return (c && c->count > 0) ? 1 : 0;
}

int main(void) {
    return (int)nx_user_main();
}
