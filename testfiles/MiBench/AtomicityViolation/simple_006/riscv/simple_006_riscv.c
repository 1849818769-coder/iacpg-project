/*
 * AtomicityViolation - simple_006 (hard)
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

volatile int state;

static int get_state(void) { return state; }
static void set_state(int v) { state = v; }

void simple_006_riscv_main(void) {
    init();
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();

    int old = get_state();
    int new_val = old + 1;
    set_state(new_val);
}

void MachineTimer_IRQHandler(void) {
    state = 0;
}
