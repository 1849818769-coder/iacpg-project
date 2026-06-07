/*
 * DivideByZero - simple_006 (hard)
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}

void init(void);
void print(int);

volatile int divisor;
volatile int safe_flag;

void simple_006_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();

    divisor = 10;
    safe_flag = 1;

    if (safe_flag) {
        __disable_irq();
    }

    if (divisor != 0) {
        print(100 / divisor);
    }

    if (safe_flag) {
        __enable_irq();
    }
}

void MachineTimer_IRQHandler(void) {
    safe_flag = 0;
    divisor = 0;
}
