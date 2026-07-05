/** VAT position over a period: collectée − déductible = à décaisser (44551). */
export interface EtatTva {
  date_from: string;
  date_to: string;
  collectee: string;
  deductible: string;
  a_decaisser: string;
}
