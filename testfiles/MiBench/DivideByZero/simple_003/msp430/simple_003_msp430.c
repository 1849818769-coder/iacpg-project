/*
 * DivideByZero - simple_003
 * Architecture: MSP430 (GCC)
 */

#include <stdint.h>

#define __interrupt

void __enable_interrupt(void) {}
void __disable_interrupt(void) {}

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

void simple_003_msp430_main(void) {
    simple_003_Init();
    __enable_interrupt();
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

#pragma vector = TIMER0_A0_VECTOR
__interrupt void simple_003_msp430_isr(void) {
    if (simple_003_global_flag != 0) {
        open_count = 1;
        close_count = 0;
    } else {
        open_count = 0;
        close_count = 1;
    }
}
