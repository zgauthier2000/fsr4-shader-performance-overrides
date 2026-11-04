// TweetNaCl wants randombytes for key making, which the kit never does.
void randombytes(unsigned char* x, unsigned long long n) { (void)x; (void)n; __builtin_trap(); }
