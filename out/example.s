    .intel_syntax noprefix
    .text
    .globl nx_fun_a
    .def    nx_fun_a;    .scl 2;    .type 32;    .endef
nx_fun_a:
    push rbp
    mov rbp, rsp
    sub rsp, 80
.L_fun_a_entry:
    mov qword ptr [rbp-8], rcx
    mov qword ptr [rbp-16], rdx
    mov rax, qword ptr [rbp-8]
    lea rax, [rax+rax*2]
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    mov qword ptr [rbp-32], rax
    mov rax, qword ptr [rbp-8]
    shl rax, 3
    mov qword ptr [rbp-40], rax
    mov rax, qword ptr [rbp-40]
    mov qword ptr [rbp-48], rax
    mov rax, qword ptr [rbp-24]
    jmp .L_fun_a_epilogue
    xor rax, rax
    jmp .L_fun_a_epilogue
.L_fun_a_epilogue:
    mov rsp, rbp
    pop rbp
    ret

    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 64
.L_main_entry:
    mov rax, 10
    mov qword ptr [rbp-8], rax
    mov rax, qword ptr [rbp-8]
    mov qword ptr [rbp-16], rax
    mov rax, 30
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    mov qword ptr [rbp-16], rax
    mov rcx, 30
    call nx_print_i32
    mov qword ptr [rbp-32], rax
    mov rax, 0
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret
