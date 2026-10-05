/**
 * 紫微斗数排盘桥接：包装 iztro，输出精炼 JSON 供 Python 侧消费。
 *
 * 用法：
 *   node ziwei-chart.mjs --json '{"solarDate":"1995-8-18","hour":9,"minute":30,"gender":"男","reference":"2026-3-19"}'
 *   node ziwei-chart.mjs  # 从 stdin 读 JSON
 */
import iztroPkg from 'iztro';

const { bySolar } = iztroPkg.astro;

function computeTimeIndex(hour, minute) {
  // iztro TIME_RANGE: 0=00:00~01:00 早子时, 12=23:00~00:00 晚子时
  if (hour === 23) return 12;
  if (hour === 0) return 0;
  return Math.floor((hour + 1) / 2);
}

function compactStar(s) {
  return {
    name: s.name,
    type: s.type,
    brightness: s.brightness || null,
    mutagen: s.mutagen || null,
  };
}

function build(solarDate, hour, minute, gender, reference) {
  const timeIndex = computeTimeIndex(hour, minute);
  const astro = bySolar(solarDate, timeIndex, gender, true, 'zh-CN');

  const houses = astro.palaces.map((p) => ({
    index: p.index,
    name: p.name,
    isBodyPalace: p.isBodyPalace,
    isOriginalPalace: p.isOriginalPalace,
    heavenlyStem: p.heavenlyStem,
    earthlyBranch: p.earthlyBranch,
    major: p.majorStars.map(compactStar),
    minor: p.minorStars.map((s) => s.name),
    adjective: p.adjectiveStars.map((s) => s.name),
    decadal: p.decadal,
    ages: p.ages,
  }));

  let decadalList = [];
  try {
    decadalList = astro.decadalList().map((d) => ({
      palaceName: d.palaceName,
      ageRange: d.ageRange,
      yearRange: d.yearRange,
      heavenlyStem: d.heavenlyStem,
      earthlyBranch: d.earthlyBranch,
      mutagen: d.mutagen || [],
    }));
  } catch (_) { /* 保留空列表 */ }

  let horoscope = null;
  if (reference) {
    try {
      const h = astro.horoscope(reference);
      horoscope = {
        decadal: {
          name: h.decadal?.name,
          heavenlyStem: h.decadal?.heavenlyStem,
          earthlyBranch: h.decadal?.earthlyBranch,
          mutagen: h.decadal?.mutagen || [],
        },
        yearly: {
          name: h.yearly?.name,
          heavenlyStem: h.yearly?.heavenlyStem,
          earthlyBranch: h.yearly?.earthlyBranch,
          mutagen: h.yearly?.mutagen || [],
          age: h.yearly?.age ?? null,
        },
      };
    } catch (_) { /* 参考时间不合法时忽略 */ }
  }

  const soulPalace = houses.find((h) => h.name === '命宫');
  const bodyPalace = houses.find((h) => h.isBodyPalace);
  const soul = soulPalace?.major?.[0]?.name ?? null;
  const body = bodyPalace?.major?.[0]?.name ?? null;

  return {
    solarDate: astro.solarDate,
    lunarDate: astro.lunarDate,
    chineseDate: astro.chineseDate,
    time: astro.time,
    timeRange: astro.timeRange,
    sign: astro.sign,
    zodiac: astro.zodiac,
    fiveElementsClass: astro.fiveElementsClass,
    soulPalaceBranch: astro.earthlyBranchOfSoulPalace,
    bodyPalaceBranch: astro.earthlyBranchOfBodyPalace,
    soul,
    body,
    houses,
    decadalList,
    horoscope,
  };
}

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (chunk) => (data += chunk));
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

async function main() {
  let input = null;
  const idx = process.argv.indexOf('--json');
  if (idx > -1) {
    input = process.argv[idx + 1];
  } else {
    input = await readStdin();
  }
  const params = JSON.parse(input);
  const result = build(
    params.solarDate,
    params.hour,
    params.minute,
    params.gender, // 男 | 女
    params.reference || null
  );
  process.stdout.write(JSON.stringify(result));
}

main().catch((err) => {
  process.stderr.write(JSON.stringify({ error: String(err && err.stack || err) }));
  process.exit(1);
});
