    .intel_syntax noprefix
    .text
    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 48
.L_main_entry:
    mov rax, 0
    mov qword ptr [rbp-8], rax
    mov rax, qword ptr [rbp-8]
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret
