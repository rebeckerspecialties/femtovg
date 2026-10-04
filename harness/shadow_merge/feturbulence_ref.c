/* Reference feTurbulence: the C code of Filter Effects Module Level 1, section
 * "feTurbulence" (from SVG 1.1), evaluated on a grid of user-space points.
 *
 *   feturbulence_ref W H a b c d e f seed bfx bfy octaves fractal(0|1) out.f32
 *
 * Pixel (i, j) of the W x H output is evaluated at the user-space point
 * (a*i + c*j + e, b*i + d*j + f); the caller folds any pixel offset into e
 * and f. Output: W*H*4 float32 in host order, the unclamped turbulence sums
 * per channel (R, G, B, A); the caller maps them to colour ((sum + 1) / 2
 * for fractalNoise, sum for turbulence) and clamps. refnoise.py builds it. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#define BSize 0x100
#define BM 0xff
#define PerlinN 0x1000
#define RAND_m 2147483647
#define RAND_a 16807
#define RAND_q 127773
#define RAND_r 2836

static int uLatticeSelector[BSize + BSize + 2];
static double fGradient[4][BSize + BSize + 2][2];

static long setup_seed(long lSeed) {
    if (lSeed <= 0) lSeed = -(lSeed % (RAND_m - 1)) + 1;
    if (lSeed > RAND_m - 1) lSeed = RAND_m - 1;
    return lSeed;
}

static long rnd(long lSeed) {
    long result = RAND_a * (lSeed % RAND_q) - RAND_r * (lSeed / RAND_q);
    if (result <= 0) result += RAND_m;
    return result;
}

static void init(long lSeed) {
    double s;
    int i, j, k;
    lSeed = setup_seed(lSeed);
    for (k = 0; k < 4; k++) {
        for (i = 0; i < BSize; i++) {
            uLatticeSelector[i] = i;
            for (j = 0; j < 2; j++)
                fGradient[k][i][j] = (double)(((lSeed = rnd(lSeed)) % (BSize + BSize)) - BSize) / BSize;
            s = sqrt(fGradient[k][i][0] * fGradient[k][i][0] + fGradient[k][i][1] * fGradient[k][i][1]);
            fGradient[k][i][0] /= s;
            fGradient[k][i][1] /= s;
        }
    }
    while (--i) {
        k = uLatticeSelector[i];
        uLatticeSelector[i] = uLatticeSelector[j = (lSeed = rnd(lSeed)) % BSize];
        uLatticeSelector[j] = k;
    }
    for (i = 0; i < BSize + 2; i++) {
        uLatticeSelector[BSize + i] = uLatticeSelector[i];
        for (k = 0; k < 4; k++)
            for (j = 0; j < 2; j++) fGradient[k][BSize + i][j] = fGradient[k][i][j];
    }
}

#define s_curve(t) (t * t * (3. - 2. * t))
#define lerp(t, a, b) (a + t * (b - a))

static double noise2(int ch, double vec[2]) {
    int bx0, bx1, by0, by1, b00, b10, b01, b11, i, j;
    double rx0, rx1, ry0, ry1, *q, sx, sy, a, b, t, u, v;
    t = vec[0] + PerlinN;
    bx0 = ((int)t) & BM;
    bx1 = (bx0 + 1) & BM;
    rx0 = t - (int)t;
    rx1 = rx0 - 1.0f;
    t = vec[1] + PerlinN;
    by0 = ((int)t) & BM;
    by1 = (by0 + 1) & BM;
    ry0 = t - (int)t;
    ry1 = ry0 - 1.0f;
    i = uLatticeSelector[bx0];
    j = uLatticeSelector[bx1];
    b00 = uLatticeSelector[i + by0];
    b10 = uLatticeSelector[j + by0];
    b01 = uLatticeSelector[i + by1];
    b11 = uLatticeSelector[j + by1];
    sx = s_curve(rx0);
    sy = s_curve(ry0);
    q = fGradient[ch][b00]; u = rx0 * q[0] + ry0 * q[1];
    q = fGradient[ch][b10]; v = rx1 * q[0] + ry0 * q[1];
    a = lerp(sx, u, v);
    q = fGradient[ch][b01]; u = rx0 * q[0] + ry1 * q[1];
    q = fGradient[ch][b11]; v = rx1 * q[0] + ry1 * q[1];
    b = lerp(sx, u, v);
    return lerp(sy, a, b);
}

static double turbulence(int ch, double x, double y, double fx, double fy, int octaves, int fractal) {
    double sum = 0, vec[2] = {x * fx, y * fy}, ratio = 1;
    for (int o = 0; o < octaves; o++) {
        double n = noise2(ch, vec);
        sum += (fractal ? n : fabs(n)) / ratio;
        vec[0] *= 2;
        vec[1] *= 2;
        ratio *= 2;
    }
    return sum;
}

int main(int argc, char **argv) {
    if (argc != 15) {
        fprintf(stderr, "usage: turb W H a b c d e f seed bfx bfy octaves fractal out.f32\n");
        return 2;
    }
    int w = atoi(argv[1]), h = atoi(argv[2]);
    double a = atof(argv[3]), b = atof(argv[4]), c = atof(argv[5]), d = atof(argv[6]);
    double e = atof(argv[7]), f = atof(argv[8]);
    long seed = (long)atof(argv[9]); /* truncated toward zero, as the spec says */
    double fx = atof(argv[10]), fy = atof(argv[11]);
    int octaves = atoi(argv[12]), fractal = atoi(argv[13]);
    init(seed);
    float *out = malloc(sizeof(float) * 4 * w * h);
    for (int j = 0; j < h; j++)
        for (int i = 0; i < w; i++) {
            double x = a * i + c * j + e, y = b * i + d * j + f;
            for (int ch = 0; ch < 4; ch++)
                out[(j * w + i) * 4 + ch] = (float)turbulence(ch, x, y, fx, fy, octaves, fractal);
        }
    FILE *fp = fopen(argv[14], "wb");
    fwrite(out, sizeof(float), 4 * w * h, fp);
    fclose(fp);
    return 0;
}
