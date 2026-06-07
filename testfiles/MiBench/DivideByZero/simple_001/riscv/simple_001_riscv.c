/*
 * DivideByZero - simple_001
 * Architecture: RISC-V (PLIC)
 */

#include <stdint.h>

typedef enum {
  MachineTimer_IRQn = 7,
  UART0_IRQn = 10
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void PLIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void PLIC_SetPriority(IRQn_Type irqn, int priority) {
  (void)irqn;
  (void)priority;
}
IRQn_Type PLIC_ClaimIRQ(void) { return MachineTimer_IRQn; }
void PLIC_CompleteIRQ(IRQn_Type irqn) { (void)irqn; }

int rand(void);
void print(int);

volatile int simple_001_d;

void simple_001_riscv_main(void) {
    simple_001_d = rand();
    if (simple_001_d != 0) {
        print(10 / simple_001_d);
    }
}

void MachineTimer_IRQHandler(void) {
    simple_001_d--;
}

static void uart0_isr(void) {
    simple_001_d--;
    if (simple_001_d <= 0) {
        simple_001_d = 1;
    }
}

void MachineExternal_IRQHandler(void) {
    IRQn_Type irq = PLIC_ClaimIRQ();
    if (irq == UART0_IRQn) {
        uart0_isr();
    }
    PLIC_CompleteIRQ(irq);
}
