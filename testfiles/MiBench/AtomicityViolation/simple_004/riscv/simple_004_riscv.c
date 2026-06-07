/*
 * atomicityViolation - simple_001
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

void init(void);
void idlerun(void);

volatile int global_var1;
volatile int global_var2;

void simple_001_riscv_main(void) {
    init();

    int x = rand();
    int y = rand();
    int z;
    int p = rand();

    if ((global_var1 < y) && (global_var1 > x))
        z = x + y;

    p == 1 ? global_var2 : global_var2;
}

void MachineExternal_IRQHandler(void) {
    idlerun();
    global_var1 = 5;
    global_var2 = 5;
}
