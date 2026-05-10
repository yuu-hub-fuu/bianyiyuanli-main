    .intel_syntax noprefix
    .text
    .globl nx_add
    .def    nx_add;    .scl 2;    .type 32;    .endef
nx_add:
    push rbp
    mov rbp, rsp
    sub rsp, 64
.L_add_entry:
    mov qword ptr [rbp-8], rcx
    mov qword ptr [rbp-16], rdx
    mov rax, qword ptr [rbp-8]
    mov rcx, qword ptr [rbp-16]
    add rax, rcx
    mov qword ptr [rbp-24], rax
    mov rax, qword ptr [rbp-24]
    jmp .L_add_epilogue
    xor rax, rax
    jmp .L_add_epilogue
.L_add_epilogue:
    mov rsp, rbp
    pop rbp
    ret

    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 256
.L_main_entry:
    mov rax, 10
    mov qword ptr [rbp-8], rax
    mov rax, 20
    mov qword ptr [rbp-16], rax
    mov rcx, 16
    call nx_alloc
    mov qword ptr [rbp-24], rax
    mov rcx, qword ptr [rbp-24]
    mov rdx, qword ptr [rbp-8]
    mov qword ptr [rcx+0], rdx
    mov rcx, qword ptr [rbp-24]
    mov rdx, qword ptr [rbp-16]
    mov qword ptr [rcx+8], rdx
    mov rax, qword ptr [rbp-24]
    mov qword ptr [rbp-32], rax
    mov rax, qword ptr [rbp-32]
    mov rax, qword ptr [rax+0]
    mov qword ptr [rbp-40], rax
    mov rax, 5
    mov qword ptr [rbp-48], rax
    mov rax, qword ptr [rbp-40]
    mov rcx, qword ptr [rbp-48]
    add rax, rcx
    mov qword ptr [rbp-56], rax
    mov rax, qword ptr [rbp-32]
    mov rcx, qword ptr [rbp-56]
    mov qword ptr [rax+0], rcx
    mov rax, 1
    mov qword ptr [rbp-64], rax
    mov rax, 2
    mov qword ptr [rbp-72], rax
    mov rax, 3
    mov qword ptr [rbp-80], rax
    mov rax, 4
    mov qword ptr [rbp-88], rax
    mov rcx, 32
    call nx_alloc
    mov qword ptr [rbp-96], rax
    mov rcx, qword ptr [rbp-96]
    mov rdx, qword ptr [rbp-64]
    mov qword ptr [rcx+0], rdx
    mov rcx, qword ptr [rbp-96]
    mov rdx, qword ptr [rbp-72]
    mov qword ptr [rcx+8], rdx
    mov rcx, qword ptr [rbp-96]
    mov rdx, qword ptr [rbp-80]
    mov qword ptr [rcx+16], rdx
    mov rcx, qword ptr [rbp-96]
    mov rdx, qword ptr [rbp-88]
    mov qword ptr [rcx+24], rdx
    mov rax, qword ptr [rbp-96]
    mov qword ptr [rbp-104], rax
    mov rax, 0
    mov qword ptr [rbp-112], rax
    mov rax, qword ptr [rbp-104]
    mov rcx, qword ptr [rbp-112]
    mov rax, qword ptr [rax+rcx*8]
    mov qword ptr [rbp-120], rax
    mov rax, 3
    mov qword ptr [rbp-128], rax
    mov rax, qword ptr [rbp-104]
    mov rcx, qword ptr [rbp-128]
    mov rax, qword ptr [rax+rcx*8]
    mov qword ptr [rbp-136], rax
    mov rax, qword ptr [rbp-120]
    mov rcx, qword ptr [rbp-136]
    add rax, rcx
    mov qword ptr [rbp-144], rax
    mov rax, 2
    mov qword ptr [rbp-152], rax
    mov rax, qword ptr [rbp-104]
    mov rcx, qword ptr [rbp-152]
    mov rdx, qword ptr [rbp-144]
    mov qword ptr [rax+rcx*8], rdx
    mov rax, 2
    mov qword ptr [rbp-160], rax
    mov rax, qword ptr [rbp-104]
    mov rcx, qword ptr [rbp-160]
    mov rax, qword ptr [rax+rcx*8]
    mov qword ptr [rbp-168], rax
    mov rcx, qword ptr [rbp-168]
    call nx_print_i32
    mov qword ptr [rbp-176], rax
    mov rax, qword ptr [rbp-32]
    mov rax, qword ptr [rax+0]
    mov qword ptr [rbp-184], rax
    mov rax, qword ptr [rbp-32]
    mov rax, qword ptr [rax+8]
    mov qword ptr [rbp-192], rax
    mov rcx, qword ptr [rbp-184]
    mov rdx, qword ptr [rbp-192]
    call nx_max__i32
    mov qword ptr [rbp-200], rax
    mov rax, 2
    mov qword ptr [rbp-208], rax
    mov rax, qword ptr [rbp-104]
    mov rcx, qword ptr [rbp-208]
    mov rax, qword ptr [rax+rcx*8]
    mov qword ptr [rbp-216], rax
    mov rcx, qword ptr [rbp-200]
    mov rdx, qword ptr [rbp-216]
    call nx_add
    mov qword ptr [rbp-224], rax
    mov rax, qword ptr [rbp-224]
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
    jne .L_max__i32_t29
.L_max__i32_fall_1:
    jmp .L_max__i32_t30
.L_max__i32_t29:
    mov rax, qword ptr [rbp-8]
    jmp .L_max__i32_epilogue
.L_max__i32_after_ret_4:
    jmp .L_max__i32_t31
.L_max__i32_t30:
    jmp .L_max__i32_t31
.L_max__i32_t31:
    mov rax, qword ptr [rbp-16]
    jmp .L_max__i32_epilogue
    xor rax, rax
    jmp .L_max__i32_epilogue
.L_max__i32_epilogue:
    mov rsp, rbp
    pop rbp
    ret
