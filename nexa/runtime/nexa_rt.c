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
#include <string.h>

extern long long nx_user_main(void);

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
