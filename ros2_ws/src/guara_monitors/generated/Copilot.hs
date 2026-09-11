import           Copilot.Compile.C99
import           Copilot.Language              hiding (prop)
import           Copilot.Language.Prelude
import           Copilot.Library.LTL           (next)
import           Copilot.Library.MTL           hiding (since, alwaysBeen, trigger)
import           Copilot.Library.PTLTL         (since, previous, alwaysBeen)
import qualified Copilot.Library.PTLTL         as PTLTL
import qualified Copilot.Library.MTL           as MTL
import           Copilot.Library.StateMachines (stateMachine)
import           Language.Copilot              (reify)
import           Prelude                       hiding ((&&), (||), (++), (<=), (>=), (<), (>), (==), (/=), not)

input_signal :: Stream (Float)
input_signal = extern "input_signal" Nothing

-- | AltitudeBelowCeiling
--   @
--   Local NED z stays at or above -2.0 m, i.e. the altitude above the local origin stays at or below the 2.0 m ceiling of the M2 bench scenario. z is down-positive. The ceiling is deliberately below the PX4 takeoff altitude (MIS_TAKEOFF_ALT, 2.5 m by default) so that the run contains both verdicts: not violated on the ground and during the first part of the climb, violated after the ceiling is crossed. A requirement that is violated from the first sample makes AC-3 vacuous (review of 2026-09-11, AC-3 gap).
--   @
propAltitudeBelowCeiling :: Stream Bool
propAltitudeBelowCeiling = input_signal >= (0.0 - 2.0)

-- | Clock that increases in one-unit steps.
clock :: Stream Int64
clock = [0] ++ (clock + 1)

-- | First Time Point
ftp :: Stream Bool
ftp = [True] ++ false

pre :: Stream Bool -> Stream Bool
pre = ([False] ++)

tpre :: Stream Bool -> Stream Bool
tpre = ([True] ++)

notPreviousNot :: Stream Bool -> Stream Bool
notPreviousNot = not . PTLTL.previous . not

-- | Complete specification. Calls C handler functions when properties are
-- violated.
spec :: Spec
spec = do
  trigger "handlerAltitudeBelowCeiling" (not propAltitudeBelowCeiling) []

main :: IO ()
main = reify spec >>= compile "copilot"
