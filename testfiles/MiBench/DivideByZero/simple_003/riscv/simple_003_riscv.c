/*
 * DivideByZero - simple_003
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

#define uchar unsigned char
#define uint unsigned int
uint open_count = 0;
uint close_count = 0;
uint simple_003_global_flag = 0;
int rand(void);
int getOpenStep(void);
int getCloseStep(void);

struct S_CONTROL_PARA {
    uint X;
    uint Y;
    uint distance;
};
struct S_CONTROL_PARA globalCtr;
struct S_CONTROL_PARA *ctr = &globalCtr;

void simple_003_Init(void) {
    open_count = rand();
    close_count = rand();
}

void simple_003_riscv_main(void) {
    simple_003_Init();
    PLIC_SetPriority(MachineTimer_IRQn, 2);
    PLIC_EnableIRQ(MachineTimer_IRQn);
    __enable_irq();
    int diff = getOpenStep();
    ctr->X += ctr->distance / diff;
    diff = getCloseStep();
    ctr->X += ctr->distance / diff;
}

int getOpenStep(void) {
    int step = 0;
    if (open_count > close_count) {
        step = open_count;
    } else {
        step = -1;
    }
    return step;
}

int getCloseStep(void) {
    int step = 0;
    if (open_count > close_count) {
        step = close_count;
    } else {
        step = -1;
    }
    return step;
}

void MachineTimer_IRQHandler(void) {
    if (simple_003_global_flag != 0) {
        open_count = 1;
        close_count = 0;
    } else {
        open_count = 0;
        close_count = 1;
    }
}
