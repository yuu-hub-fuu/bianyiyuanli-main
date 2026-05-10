    .intel_syntax noprefix
    .text
    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 176
.L_main_entry:
    mov rax, 1
    mov qword ptr [rbp-8], rax
    mov rcx, qword ptr [rbp-8]
    call nx_chan_new
    mov qword ptr [rbp-16], rax
    mov rax, qword ptr [rbp-16]
    mov qword ptr [rbp-24], rax
    mov rax, 42
    mov qword ptr [rbp-32], rax
    mov rcx, qword ptr [rbp-24]
    mov rdx, qword ptr [rbp-32]
    call nx_chan_send
    mov qword ptr [rbp-40], rax
    mov rcx, qword ptr [rbp-24]
    call nx_chan_ready
    test rax, rax
    jne .L_main_t6
.L_main_fall_1:
    jmp .L_main_t7
.L_main_t6:
    mov rcx, qword ptr [rbp-24]
    call nx_chan_recv
    mov qword ptr [rbp-48], rax
    mov rax, 42
    mov qword ptr [rbp-56], rax
    mov rax, qword ptr [rbp-56]
    mov qword ptr [rbp-64], rax
    jmp .L_main_t8
.L_main_t7:
    mov rax, 0
    mov qword ptr [rbp-72], rax
    mov rax, qword ptr [rbp-72]
    mov qword ptr [rbp-64], rax
.L_main_t8:
    mov rax, qword ptr [rbp-64]
    mov qword ptr [rbp-80], rax
    mov rax, 42
    mov qword ptr [rbp-88], rax
    mov rax, qword ptr [rbp-80]
    mov rcx, qword ptr [rbp-88]
    cmp rax, rcx
    sete al
    movzx rax, al
    mov qword ptr [rbp-96], rax
    mov rax, qword ptr [rbp-96]
    cmp rax, 0
    sete al
    movzx rax, al
    mov qword ptr [rbp-104], rax
    mov rax, qword ptr [rbp-104]
    test rax, rax
    jne .L_main_t16
.L_main_fall_7:
    jmp .L_main_t17
.L_main_t16:
    lea rax, [rip+.LCstr0]
    mov qword ptr [rbp-112], rax
    mov rcx, qword ptr [rbp-112]
    call nx_panic
    mov qword ptr [rbp-120], rax
    jmp .L_main_t18
.L_main_t17:
    jmp .L_main_t18
.L_main_t18:
    mov rax, 40
    mov qword ptr [rbp-128], rax
    mov rcx, qword ptr [rbp-80]
    mov rdx, qword ptr [rbp-128]
    call nx_max__i32
    mov qword ptr [rbp-136], rax
    mov rax, qword ptr [rbp-136]
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret

    .globl nx_max__i32
    .def    nx_max__i32;    .scl 2;    .type 32;    .endef
nx_max__i32:
    push rbp
    mov rbp, rsp
    sub rsp, 64
.L_max__i32_entry:
    mov qword ptr [rbp-8], rcx
    mov qword ptr [rbp-16], rdx
    mov rax, qword ptr [rbp-8]
    mov rcx, qword ptr [rbp-16]
    cmp rax, rcx
    setg al
    movzx rax, al
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    test rax, rax
    jne .L_max__i32_t24
.L_max__i32_fall_1:
    jmp .L_max__i32_t25
.L_max__i32_t24:
    mov rax, qword ptr [rbp-8]
    jmp .L_max__i32_epilogue
.L_max__i32_after_ret_4:
    jmp .L_max__i32_t26
.L_max__i32_t25:
    jmp .L_max__i32_t26
.L_max__i32_t26:
    mov rax, qword ptr [rbp-16]
    jmp .L_max__i32_epilogue
    xor rax, rax
    jmp .L_max__i32_epilogue
.L_max__i32_epilogue:
    mov rsp, rbp
    pop rbp
    ret


    .section .rodata
    .p2align 3
.LCstr0:
    .asciz "bad"
