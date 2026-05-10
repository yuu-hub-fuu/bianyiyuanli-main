    .intel_syntax noprefix
    .text
    .globl nx_quad
    .def    nx_quad;    .scl 2;    .type 32;    .endef
nx_quad:
    push rbp
    mov rbp, rsp
    sub rsp, 80
.L_quad_entry:
    movsd qword ptr [rbp-8], xmm0
    movsd qword ptr [rbp-16], xmm1
    movsd qword ptr [rbp-24], xmm2
    movsd xmm0, qword ptr [rbp-8]
    movsd xmm1, qword ptr [rbp-16]
    mulsd xmm0, xmm1
    movsd qword ptr [rbp-32], xmm0
    movsd xmm0, qword ptr [rbp-32]
    movsd xmm1, qword ptr [rbp-24]
    addsd xmm0, xmm1
    movsd qword ptr [rbp-40], xmm0
    movsd xmm0, qword ptr [rbp-40]
    jmp .L_quad_epilogue
    xorpd xmm0, xmm0
    jmp .L_quad_epilogue
.L_quad_epilogue:
    mov rsp, rbp
    pop rbp
    ret

    .globl nx_user_main
    .def    nx_user_main;    .scl 2;    .type 32;    .endef
nx_user_main:
    push rbp
    mov rbp, rsp
    sub rsp, 208
.L_main_entry:
    movsd xmm0, qword ptr [rip+.LCflt0]
    movsd qword ptr [rbp-8], xmm0
    movsd xmm0, qword ptr [rip+.LCflt1]
    movsd qword ptr [rbp-16], xmm0
    movsd xmm0, qword ptr [rbp-8]
    movsd xmm1, qword ptr [rbp-16]
    addsd xmm0, xmm1
    movsd qword ptr [rbp-24], xmm0
    mov rax, qword ptr [rbp-24]
    mov qword ptr [rbp-32], rax
    movsd xmm0, qword ptr [rbp-32]
    call nx_print_f64
    mov qword ptr [rbp-40], rax
    movsd xmm0, qword ptr [rip+.LCflt2]
    movsd qword ptr [rbp-48], xmm0
    movsd xmm0, qword ptr [rip+.LCflt3]
    movsd qword ptr [rbp-56], xmm0
    movsd xmm0, qword ptr [rip+.LCflt4]
    movsd qword ptr [rbp-64], xmm0
    movsd xmm0, qword ptr [rbp-48]
    movsd xmm1, qword ptr [rbp-56]
    movsd xmm2, qword ptr [rbp-64]
    call nx_quad
    movsd qword ptr [rbp-72], xmm0
    mov rax, qword ptr [rbp-72]
    mov qword ptr [rbp-80], rax
    movsd xmm0, qword ptr [rbp-80]
    call nx_print_f64
    mov qword ptr [rbp-88], rax
    movsd xmm0, qword ptr [rip+.LCflt5]
    movsd qword ptr [rbp-96], xmm0
    movsd xmm0, qword ptr [rbp-32]
    movsd xmm1, qword ptr [rbp-96]
    ucomisd xmm0, xmm1
    seta al
    movzx rax, al
    mov qword ptr [rbp-104], rax
    mov rax, qword ptr [rbp-104]
    test rax, rax
    jne .L_main_t14
.L_main_fall_1:
    jmp .L_main_t15
.L_main_t14:
    mov rax, 1
    mov qword ptr [rbp-112], rax
    mov rcx, qword ptr [rbp-112]
    call nx_print_i32
    mov qword ptr [rbp-120], rax
    jmp .L_main_t16
.L_main_t15:
    mov rax, 0
    mov qword ptr [rbp-128], rax
    mov rcx, qword ptr [rbp-128]
    call nx_print_i32
    mov qword ptr [rbp-136], rax
    jmp .L_main_t16
.L_main_t16:
    movsd xmm0, qword ptr [rip+.LCflt6]
    movsd qword ptr [rbp-144], xmm0
    movsd xmm0, qword ptr [rbp-80]
    movsd xmm1, qword ptr [rbp-144]
    ucomisd xmm0, xmm1
    sete al
    movzx rax, al
    mov qword ptr [rbp-152], rax
    mov rax, qword ptr [rbp-152]
    test rax, rax
    jne .L_main_t23
.L_main_fall_8:
    jmp .L_main_t24
.L_main_t23:
    mov rax, 42
    mov qword ptr [rbp-160], rax
    mov rax, qword ptr [rbp-160]
    jmp .L_main_epilogue
.L_main_after_ret_11:
    jmp .L_main_t25
.L_main_t24:
    jmp .L_main_t25
.L_main_t25:
    mov rax, 7
    mov qword ptr [rbp-168], rax
    mov rax, qword ptr [rbp-168]
    jmp .L_main_epilogue
    xor rax, rax
    jmp .L_main_epilogue
.L_main_epilogue:
    mov rsp, rbp
    pop rbp
    ret


    .section .rodata
    .p2align 3
    .p2align 3
.LCflt0:
    .double 1.5
    .p2align 3
.LCflt1:
    .double 2.25
    .p2align 3
.LCflt2:
    .double 2.0
    .p2align 3
.LCflt3:
    .double 3.5
    .p2align 3
.LCflt4:
    .double 0.5
    .p2align 3
.LCflt5:
    .double 3.0
    .p2align 3
.LCflt6:
    .double 7.5
