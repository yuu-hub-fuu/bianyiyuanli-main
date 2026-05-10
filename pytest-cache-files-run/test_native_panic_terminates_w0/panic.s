    .intel_syntax noprefix
    .text
    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 64
.L_main_entry:
    lea rax, [rip+.LCstr0]
    mov qword ptr [rbp-8], rax
    mov rcx, qword ptr [rbp-8]
    call nx_panic
    mov qword ptr [rbp-16], rax
    mov rax, 0
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret


    .section .rodata
    .p2align 3
.LCstr0:
    .asciz "boom"
