/*
 * DivideByZero - simple_004
 * Architecture: ARM (Cortex-M / CMSIS)
 */

#include <stdint.h>

typedef enum {
  TIM2_IRQn = 28
} IRQn_Type;

void __enable_irq(void) {}
void __disable_irq(void) {}
void NVIC_EnableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_DisableIRQ(IRQn_Type irqn) { (void)irqn; }
void NVIC_SetPriority(IRQn_Type irqn, int priority) {
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

void simple_004_arm_main(void) {
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

void TIM2_IRQHandler(void) {
    char input_buf[6] = "";
    if (fgets(input_buf, 6, stdin) != 0) {
        data = atoi(input_buf);
    } else {
        printLine("fgets() failed.");
    }
}
