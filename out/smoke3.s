    .intel_syntax noprefix
    .text
    .globl nx_fact
    .def    nx_fact;    .scl 2;    .type 32;    .endef
nx_fact:
    push rbp
    mov rbp, rsp
    sub rsp, 112
.L_fact_entry:
    mov qword ptr [rbp-8], rcx
    mov rax, 1
    mov qword ptr [rbp-16], rax
    mov rax, qword ptr [rbp-16]
    mov qword ptr [rbp-24], rax
    mov rax, 2
    mov qword ptr [rbp-32], rax
    mov rax, qword ptr [rbp-32]
    mov qword ptr [rbp-40], rax
.L_fact_t3:
    mov rax, qword ptr [rbp-40]
    mov rcx, qword ptr [rbp-8]
    cmp rax, rcx
    setle al
    movzx rax, al
    mov qword ptr [rbp-48], rax
    mov rax, qword ptr [rbp-48]
    test rax, rax
    jne .L_fact_t4
.L_fact_fall_2:
    jmp .L_fact_t5
.L_fact_t4:
    mov rax, qword ptr [rbp-24]
    mov rcx, qword ptr [rbp-40]
    imul rax, rcx
    mov qword ptr [rbp-56], rax
    mov rax, qword ptr [rbp-56]
    mov qword ptr [rbp-24], rax
    mov rax, 1
    mov qword ptr [rbp-64], rax
    mov rax, qword ptr [rbp-40]
    mov rcx, qword ptr [rbp-64]
    add rax, rcx
    mov qword ptr [rbp-72], rax
    mov rax, qword ptr [rbp-72]
    mov qword ptr [rbp-40], rax
    jmp .L_fact_t3
.L_fact_t5:
    mov rax, qword ptr [rbp-24]
    jmp .L_fact_epilogue
    xor rax, rax
    jmp .L_fact_epilogue
.L_fact_epilogue:
    mov rsp, rbp
    pop rbp
    ret

    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 144
.L_main_entry:
    mov rax, 6
    mov qword ptr [rbp-8], rax
    mov rax, qword ptr [rbp-8]
    mov qword ptr [rbp-16], rax
    mov rcx, qword ptr [rbp-16]
    call nx_fact
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    mov qword ptr [rbp-32], rax
    mov rcx, qword ptr [rbp-32]
    call nx_print_i32
    mov qword ptr [rbp-40], rax
    mov rax, 100
    mov qword ptr [rbp-48], rax
    mov rax, qword ptr [rbp-32]
    mov rcx, qword ptr [rbp-48]
    cmp rax, rcx
    setg al
    movzx rax, al
    mov qword ptr [rbp-56], rax
    mov rax, qword ptr [rbp-56]
    test rax, rax
    jne .L_main_t15
.L_main_fall_1:
    jmp .L_main_t16
.L_main_t15:
    mov rax, 1
    mov qword ptr [rbp-64], rax
    mov rcx, qword ptr [rbp-64]
    call nx_print_i32
    mov qword ptr [rbp-72], rax
    jmp .L_main_t17
.L_main_t16:
    mov rax, 0
    mov qword ptr [rbp-80], rax
    mov rcx, qword ptr [rbp-80]
    call nx_print_i32
    mov qword ptr [rbp-88], rax
    jmp .L_main_t17
.L_main_t17:
    mov rax, 100
    mov qword ptr [rbp-96], rax
    mov rax, qword ptr [rbp-32]
    mov rcx, qword ptr [rbp-96]
    cqo
    idiv rcx
    mov rax, rdx
    mov qword ptr [rbp-104], rax
    mov rax, qword ptr [rbp-104]
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret
