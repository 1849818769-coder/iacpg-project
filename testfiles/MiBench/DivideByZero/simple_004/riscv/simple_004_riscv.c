/*
 * DivideByZero - simple_004
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

int stdin;
int data = -1;
static int static_five = 5;
extern int fgets(char * stream, int sz, int s);
extern int atoi(char * stream);
extern void printLine(char * stream);
extern void printIntLine(int);

void simple_004_riscv_main(void) {
    if (static_five == 5) {
        {
            char input_buf[6] = "";
            if (fgets(input_buf, 6, stdin) != 0) {
                data = atoi(input_buf);
            } else {
                printLine("fgets() failed.");
            }
        }
    } else {
        data = 7;
    }
    if (static_five == 5) {
        if (data != 0) {
            printIntLine(100 / data);
        } else {
            printIntLine(100);
        }
    }
}

void MachineTimer_IRQHandler(void) {
    char input_buf[6] = "";
    if (fgets(input_buf, 6, stdin) != 0) {
        data = atoi(input_buf);
    } else {
        printLine("fgets() failed.");
    }
}
