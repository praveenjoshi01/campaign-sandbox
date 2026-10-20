# The Thanksgiving Ad That Admitted Its Flaws Won, and Why I Don't Trust My Own Simulation Yet

*I ran 20 synthetic shoppers through six HP gaming-laptop ads, entirely on my own machine. 13 of 20 picked the one that confessed the product's weaknesses. Here is what that tells me, and what it doesn't.*

![The simulation in 28 seconds](https://raw.githubusercontent.com/praveenjoshi01/campaign-sandbox/main/docs/img/hp-thanksgiving-simulation.gif)

**13 of 20.**

That is how many simulated shoppers ranked the same ad first. It was not the spec sheet. It was not the doorbuster. It was the ad that opened with "Plastic body. Modest screen colors."

I did not expect that, and I trust it less the longer I look at it. So this post is half result, half post-mortem.

## The setup: one laptop, one holiday, six ads

Thanksgiving is Thursday, 26 November 2026. Black Friday is the next day, Cyber Monday the Monday after. If you sell gaming laptops, that is your week.

I picked the **HP Victus 15 with an RTX 5050** because it is the sort of laptop a Thanksgiving promotion is built around: HP's lower-priced gaming line, well below the OMEN range that starts around $1,299. I read two independent lab reviews (Notebookcheck and LaptopMedia) and wrote only what they support into the product brief:

- RTX 5050 with 8 GB, 15.6-inch Full HD at 144 Hz
- **176 FPS** in Counter-Strike 2 at 1080p Very High, measured by LaptopMedia
- two RAM slots and two SSD slots, so it is upgradeable
- weak points: a plastic body, and color coverage of only 57 to 64 percent sRGB

**One disclosure matters.** This is an independent experiment. The **$799 price and the Thanksgiving-to-Cyber-Monday window are my assumptions**, marked as such in the brief. They are not an HP offer.

Then I wrote six ads, each pulling a different lever:

1. **Spec sheet** (the control): the facts and the price
2. **Measured proof**: "176 frames per second in Counter-Strike 2, measured by an independent lab"
3. **Upgradeable**: "buy it now, upgrade it later"
4. **Gift framing**: "the Thanksgiving gift that works for school and game night"
5. **Candid trade-offs**: "Plastic body. Modest screen colors. Serious RTX 5050 graphics for the money."
6. **Urgency**: "BLACK FRIDAY DOORBUSTER... hurry!"

## How the simulation works

I took the loop from [MiroFish](https://github.com/666ghj/MiroFish), seed, graph, personas, simulate, report, and shrank it until it fit on one machine with no API bill. A local 27B Qwen model runs through Ollama on a Mac with an M5 Pro chip. About 45 model calls in total.

- **The brief becomes a fact list.** The model extracts the checkable facts, with numbers, and that list is the only product knowledge personas get.
- **20 personas across four segments**: students on a budget, parents buying a gift, competitive players, and people who work and play on one machine. Each has a fixed name and life situation, so I do not get twenty copies of the same person.
- **Round 1:** every persona sees all six ads in a shuffled order, ranks them, and picks the one they would click, or none.
- **Round 2:** each persona reads three peers' reactions, then ranks again.

I also wrote five success tests up front, such as "measured proof beats the spec sheet" and "gift framing beats the spec sheet with parents", so I could not rationalize afterwards.

## What came out

After peers weighed in, the average position of each ad (1 is best):

- **Candid trade-offs: 1.65.** First choice for 13 of 20.
- **Upgradeable: 2.25**
- **Gift framing: 3.05**
- **Spec sheet: 4.00**
- **Measured proof: 4.20**
- **Urgency: 5.85.** Last for 17 of 20.

![Who ranks each ad first](https://raw.githubusercontent.com/praveenjoshi01/campaign-sandbox/main/docs/img/4-votes.png)

Four of my five tests passed. The one that failed is the interesting one: **measured proof did not beat the plain spec sheet overall.**

Then I split by audience, and the failure made sense:

![Segment results](https://raw.githubusercontent.com/praveenjoshi01/campaign-sandbox/main/docs/img/5-segments.png)

- **Competitive players** ranked measured proof 2.8. **Parents buying a gift** ranked it 5.0. Same ad, same words.
- **Parents** were the only group where **gift framing** came first (1.8).
- All five **students** ranked the candid ad first. Not one defected.

This is the finding I would actually act on: **there is no best ad, only a best ad per audience.** A single blended "winner" hides it.

One competitive player, Brendan, put the proof ad first but still pushed back on it: a raw FPS number "without context on thermals or frame time consistency is a trap." One parent, Ravi, wrote that a "transparent confession of flaws like 'plastic body' or 'modest screen'" "signals low quality to me." Both are things a real shopper could say.

## Why I don't trust the headline

Here is the uncomfortable part. When I read the round 1 reasoning, **16 of 20 personas used honesty language, and 10 wrote some version of "respects my intelligence."**

Language models are trained to value candor. My personas inherit that taste. Real shoppers on Black Friday also tend to respond to a price drop and a ticking clock, and retailers keep running doorbusters. A simulation that ranks urgency last for 17 of 20 people is telling me about the model as much as about the market.

So I read the 13 of 20 as a hypothesis about **wording to test**, not a prediction of **conversion**. Three personas did not put urgency last, and I would be careful about how much weight three people can carry.

Peer influence was small, too: only 3 of 20 changed their top pick.

## Four bugs the simulation taught me

I am more confident in the method because of what broke:

1. **A floor effect.** On my first test product, scoring each ad 1 to 5 on its own put everything at 1.0 to 1.4. The fix was **forced ranking**: all ads side by side.
2. **A numbering bug in round 2.** Peers' quotes said "Ad 5 is best," but their Ad 5 was not the reader's Ad 5. I caught it by reading the quotes, fixed it, and reran. The conclusions barely moved.
3. **Facts that dropped their numbers.** My first graph kept relations but lost prices and specs, so personas could not verify anything. I switched to an explicit checkable-facts list.
4. **Four personas named "Marcus Thorne."** Left alone, the model reuses names and backgrounds. I now assign them in code.

## Swap in your own product

Everything product-specific lives in a project folder. Four files, three commands.

```text
projects/my_product/
  project.json     scenario shown to personas, scale wording
  product.md       the brief (the only facts personas may use)
  campaigns.json   hypothesis, ad variants, success tests
  segments.json    audiences and the life situations inside them
```

A success test is just data:

```json
{ "label": "Gift framing beats the spec sheet with parents",
  "better": "D_gift", "worse": "A_spec_sheet", "by": 0.3,
  "segment": "parent_gift_buyer" }
```

```bash
python3 check_project.py my_product             # warns when an ad claims a number the brief lacks
python3 -u poc.py my_product 5                  # graph -> personas -> two rounds -> report
python3 make_ui.py my_product                   # console page
```

The checker flags any number in an ad that does not appear in the brief, and it lists every assumption you marked, so nothing invented slips into an ad unnoticed.

## What I would do next

- **Add a real deal-heavy control** and strip the "be blunt, ads are mostly ignored" line from the persona prompt, which probably pushes them toward skepticism. If urgency still comes last, that means something.
- **Feed the brief from competitor intelligence**, like the playbook teardown I wrote about [here](https://praveenjoshi007.medium.com/i-built-an-ai-that-reverse-engineers-your-competitors-entire-marketing-playbook-in-one-click-537f77f6b2dc), so personas judge my ad against what they have actually seen.
- **Run the real thing.** The only number that counts is conversion from a live A/B test of the top two or three wordings.

## Questions for you

- Would you run a candid ad like this to your own customers, or does it feel risky?
- What do you check before you believe a synthetic-user result?
- Which segment would you add for a laptop campaign?

The code, both example runs, and the animation are open source: **[github.com/praveenjoshi01/campaign-sandbox](https://github.com/praveenjoshi01/campaign-sandbox)**.

---

*Sources: Notebookcheck's lab review of the HP Victus 15 with RTX 5050 (27 Oct 2025); LaptopMedia's review of the Victus 15 (15-fb3000); FinalBoss' RTX 5050 laptop roundup; GamesRadar's early Black Friday 2026 coverage. All simulated shoppers are language-model personas and say nothing about real buyers until tested.*
