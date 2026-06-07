/*
 * DivideByZero - simple_005 (hard)
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

volatile int raw_divisor;

static int get_divisor(void) { return raw_divisor; }

void simple_005_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();

    raw_divisor = 10;

    if (raw_divisor != 0) {
        int d = get_divisor();
        print(100 / d);
    }
}

void MachineTimer_IRQHandler(void) {
    raw_divisor = 0;
}
